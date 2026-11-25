# MDM RT helpers: libopus (BSD) as a static library, for ffmpeg's libopus encoder: MDM's "Audio only" Opus choice
# runs yt-dlp -x --audio-format opus, which asks ffmpeg for -acodec libopus when the site's sound is not Opus already
# (AAC from Vimeo, X, Instagram ...; YouTube's Opus is only copied).
#
#   python -I build-opus.py <arm32|x86> <opus source> <prefix dir>
#
# <opus source>: the Opus tree Chromium (so Venetium) builds, third_party/opus/src (revision 55513e81, 1.5 series);
# read only. The file list is Chromium's BUILD.gn "opus" target (float build, as Chromium's on Windows), and its
# defines without ENABLE_HARDENING; ARM32: the NEON intrinsics files with OPUS_ARM_MAY_HAVE/PRESUME_NEON_INTR (no
# hand-written assembly, no run-time CPU detection: every Windows ARM32 CPU has NEON). Output: <prefix>\lib\opus.lib,
# <prefix>\include\opus\*.h (pkg-config's layout: ffmpeg includes <opus.h> with -I<prefix>\include\opus) and
# <prefix>\COPYING-opus.txt.
import argparse, concurrent.futures, ctypes, os, shutil, subprocess, sys

RT = os.environ.get('RT_TOOLCHAIN', r'F:\cr\rt24-cr')
VC = os.environ.get('RT_VCTOOLS', r'D:\Program Files\vs22buildtools\VC\Tools\MSVC\14.44.35207')
SDK = os.environ.get('RT_WINSDK', r'D:\Windows Kits\10')
SDKINC = '10.0.26100.0'
TARGET = {'arm32': 'armv7-pc-windows-msvc', 'x86': 'i686-pc-windows-msvc'}
VERSION = '1.5-chromium-55513e81'
CELT = 'bands celt celt_decoder celt_encoder celt_lpc cwrs entcode entdec entenc kiss_fft laplace mathops mdct modes ' \
       'pitch quant_bands rate vq'
SILK = 'A2NLSF CNG HP_variable_cutoff LPC_analysis_filter LPC_fit LPC_inv_pred_gain LP_variable_cutoff NLSF2A NLSF_VQ ' \
       'NLSF_VQ_weights_laroia NLSF_decode NLSF_del_dec_quant NLSF_encode NLSF_stabilize NLSF_unpack NSQ NSQ_del_dec ' \
       'PLC VAD VQ_WMat_EC ana_filt_bank_1 biquad_alt bwexpander bwexpander_32 check_control_input code_signs ' \
       'control_SNR control_audio_bandwidth control_codec debug dec_API decode_core decode_frame decode_indices ' \
       'decode_parameters decode_pitch decode_pulses decoder_set_fs enc_API encode_indices encode_pulses gain_quant ' \
       'init_decoder init_encoder inner_prod_aligned interpolate lin2log log2lin pitch_est_tables process_NLSFs ' \
       'quant_LTP_gains resampler resampler_down2 resampler_down2_3 resampler_private_AR2 ' \
       'resampler_private_IIR_FIR resampler_private_down_FIR resampler_private_up2_HQ resampler_rom shell_coder ' \
       'sigm_Q15 sort stereo_LR_to_MS stereo_MS_to_LR stereo_decode_pred stereo_encode_pred stereo_find_predictor ' \
       'stereo_quant_pred sum_sqr_shift table_LSF_cos tables_LTP tables_NLSF_CB_NB_MB tables_NLSF_CB_WB tables_gain ' \
       'tables_other tables_pitch_lag tables_pulses_per_block'
SILK_FLP = 'LPC_analysis_filter_FLP LPC_inv_pred_gain_FLP LTP_analysis_filter_FLP LTP_scale_ctrl_FLP ' \
           'apply_sine_window_FLP autocorrelation_FLP burg_modified_FLP bwexpander_FLP corrMatrix_FLP ' \
           'encode_frame_FLP energy_FLP find_LPC_FLP find_LTP_FLP find_pitch_lags_FLP find_pred_coefs_FLP ' \
           'inner_product_FLP k2a_FLP noise_shape_analysis_FLP pitch_analysis_core_FLP process_gains_FLP ' \
           'regularize_correlations_FLP residual_energy_FLP scale_copy_vector_FLP scale_vector_FLP schur_FLP ' \
           'sort_FLP warped_autocorrelation_FLP wrappers_FLP'
SRC = 'analysis extensions mapping_matrix mlp mlp_data opus opus_decoder opus_encoder opus_multistream ' \
      'opus_multistream_decoder opus_multistream_encoder opus_projection_decoder opus_projection_encoder repacketizer'
ARM_NEON = ['celt/arm/celt_neon_intr.c', 'celt/arm/pitch_neon_intr.c', 'silk/arm/LPC_inv_pred_gain_neon_intr.c',
            'silk/arm/NSQ_del_dec_neon_intr.c', 'silk/arm/NSQ_neon.c', 'silk/arm/biquad_alt_neon_intr.c']


def pgo_flags(pgo, src):
    """clang-cl flags for --pgo: none, gen (counting build) or use=<profdata> (+ ThinLTO, as ffmpeg-rt's use build).
    Static functions are named by their file relative to the source folder (-static-func-strip-dirname-prefix =
    the folder's separator count), so a profile fits any checkout."""
    if pgo == 'none':
        return []
    strip = ['-mllvm', '-static-func-strip-dirname-prefix=%d' % sum(c in '/\\' for c in src.rstrip('/\\') + '\\')]
    if pgo == 'gen':
        return ['-fprofile-generate'] + strip
    if pgo.startswith('use='):
        prof = pgo[4:]
        if not os.path.isfile(prof):
            sys.exit('no profile ' + prof)
        return ['-fprofile-use=' + prof, '-flto=thin', '-mllvm', '-pgso=false', '-Wno-profile-instr-unprofiled',
                '-Wno-profile-instr-out-of-date', '-Wno-backend-plugin'] + strip
    sys.exit('--pgo: none, gen or use=<profdata>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('arch', choices=sorted(TARGET))
    ap.add_argument('src')
    ap.add_argument('prefix')
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument('--pgo', default='none', help='none, gen (counting build) or use=<profdata>')
    a = ap.parse_args()
    try:
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)  # below normal
    except Exception:
        pass
    src, pfx = os.path.abspath(a.src), os.path.abspath(a.prefix)
    if not os.path.isfile(os.path.join(src, 'include', 'opus.h')) or not os.path.isdir(os.path.join(src, 'silk', 'float')):
        sys.exit(src + ' is not an Opus source tree')
    build = os.path.join(pfx, 'build')
    if os.path.exists(build):
        sys.exit(build + ' exists already (use a new prefix)')
    os.makedirs(build)
    files = (['celt/%s.c' % n for n in CELT.split()] + ['silk/%s.c' % n for n in SILK.split()] +
             ['silk/float/%s.c' % n for n in SILK_FLP.split()] + ['src/%s.c' % n for n in SRC.split()])
    defines = ['OPUS_BUILD', 'OPUS_EXPORT=', 'USE_ALLOCA', 'HAVE_LRINT', 'HAVE_LRINTF', 'NDEBUG',
               'PACKAGE_VERSION="%s"' % VERSION, '_CRT_SECURE_NO_WARNINGS']
    if a.arch == 'arm32':
        files += ARM_NEON
        defines += ['OPUS_ARM_MAY_HAVE_NEON_INTR', 'OPUS_ARM_PRESUME_NEON_INTR']
    missing = [f for f in files if not os.path.isfile(os.path.join(src, f))]
    if missing:
        sys.exit('missing in %s: %s' % (src, missing))
    cl = os.path.join(RT, 'bin', 'clang-cl.exe')
    base = [cl, '--target=' + TARGET[a.arch], '-vctoolsdir', VC, '-winsdkdir', SDK, '-winsdkversion', SDKINC,
            '-nologo', '-MT', '-O2', '-w'] + ['-D' + d for d in defines] + \
           ['-I' + os.path.join(src, d) for d in ('include', '.', 'celt', 'silk', 'silk/fixed', 'silk/float')] + ['-c']

    def compile_one(rel):
        obj = os.path.join(build, rel.replace('/', '_')[:-2] + '.obj')
        r = subprocess.run(base + ['-Fo' + obj, os.path.join(src, rel)], capture_output=True)
        return rel, obj, r.returncode, (r.stdout + r.stderr).decode('utf-8', 'replace')

    objs = []
    base += pgo_flags(a.pgo, src)
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as ex:
        for rel, obj, rc, out in ex.map(compile_one, files):
            if rc:
                sys.exit('%s failed:\n%s' % (rel, out))
            objs.append(obj)
    os.makedirs(os.path.join(pfx, 'lib'), exist_ok=True)
    inc = os.path.join(pfx, 'include', 'opus')
    os.makedirs(inc, exist_ok=True)
    lib = os.path.join(pfx, 'lib', 'opus.lib')
    subprocess.run([os.path.join(RT, 'bin', 'llvm-ar.exe'), 'rcs', lib] + objs, check=True)
    for h in ('opus.h', 'opus_defines.h', 'opus_multistream.h', 'opus_projection.h', 'opus_types.h'):
        shutil.copy2(os.path.join(src, 'include', h), os.path.join(inc, h))
    shutil.copy2(os.path.join(src, 'COPYING'), os.path.join(pfx, 'COPYING-opus.txt'))
    with open(os.path.join(pfx, 'VERSION'), 'w') as f:
        f.write(VERSION + '\n')
    print('%s: %s (%d objects, %d bytes)' % (a.arch, lib, len(objs), os.path.getsize(lib)))


if __name__ == '__main__':
    main()
