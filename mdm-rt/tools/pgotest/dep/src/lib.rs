pub fn work(n: u64) -> u64 {
    let mut a = 0u64;
    for i in 0..n {
        if i % 7 == 3 { a = a.wrapping_mul(31).wrapping_add(i); } else { a ^= i << 3; }
    }
    a
}
