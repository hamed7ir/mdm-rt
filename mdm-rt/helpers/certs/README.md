# helpers/certs: the root certificates yt-dlp trusts on ARM32

`cacert.pem` is Mozilla's list of root certificates for TLS servers (121 roots), as MSYS2's `ca-certificates`
package 20260816-1 extracts it from Mozilla's NSS (`p11-kit extract`, server authentication; built 2026-08-18),
sha256 `f345ac0d7dbd1a584dd80ff96eb2919e8dac68e962db2e7111401b434e888493`. Mozilla's list:
https://www.mozilla.org/en-US/about/governance/policies/security-group/certs/ (Mozilla Public License 2.0).

`build-helpers.py` puts it beside the yt-dlp launcher (`helpers\cacert.pem`, with `licenses\cacert.txt`), and the
launcher (`pylauncher/pylauncher.c`) names it in `SSL_CERT_FILE` for Python, whose `ssl` then trusts Windows' store
and this list. Windows' store alone failed on a Surface 2's Windows 10 build 15035 (`CERTIFICATE_VERIFY_FAILED` on
YouTube's API): an old Windows has today's roots only once a program checking certificates the Windows way has
asked for them, while Python reads the store as it is. The official yt-dlp.exe brings Mozilla's list as well
(Python's certifi); the zipapp MDM RT runs doesn't.

To refresh it: take the newer `ca-certificates` package's `/usr/ssl/certs/ca-bundle.crt` from MSYS2 (or curl's
https://curl.se/ca/cacert.pem, the same list), check its count and a few roots (`openssl crl2pkcs7 -nocrl
-certfile cacert.pem | openssl pkcs7 -print_certs -noout`), and update the version and sha256 above.
