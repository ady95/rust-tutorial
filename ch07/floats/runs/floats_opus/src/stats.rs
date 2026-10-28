//! 내장 `sum`/`min`/`max` 와 `statistics.mean`/`statistics.stdev` 의 계산 방식을 그대로 따른다.
//!
//! `statistics` 는 각 float 를 정확한 분수로 바꿔 계산한 뒤 마지막에 한 번만 올바르게 반올림한다.
//! 모든 유한 float 는 2^-1074 의 정수배이므로, 여기서는 값을 2^1074 배 한 큰 정수로 다룬다.

use crate::bigint::BigUint;

const SCALE: i64 = 1074;

/// 내장 `sum(numbers)` (CPython 3.12: Neumaier 보정 합).
pub fn py_sum(numbers: &[f64]) -> f64 {
    // 시작값은 int 0 이므로 첫 원소는 `0 + x` 가 된다(-0.0 은 0.0 으로 바뀐다).
    let mut f = 0.0 + numbers[0];
    let mut c = 0.0f64;
    for &x in &numbers[1..] {
        let t = f + x;
        if f.abs() >= x.abs() {
            c += (f - t) + x;
        } else {
            c += (x - t) + f;
        }
        f = t;
    }
    if c != 0.0 && c.is_finite() {
        f += c;
    }
    f
}

/// 내장 `min`: 첫 원소에서 시작해 더 작은 값이 나올 때만 바꾼다.
pub fn py_min(numbers: &[f64]) -> f64 {
    numbers[1..]
        .iter()
        .fold(numbers[0], |cur, &x| if x < cur { x } else { cur })
}

/// 내장 `max`: 첫 원소에서 시작해 더 큰 값이 나올 때만 바꾼다.
pub fn py_max(numbers: &[f64]) -> f64 {
    numbers[1..]
        .iter()
        .fold(numbers[0], |cur, &x| if x > cur { x } else { cur })
}

/// 유한 float 를 (음수 여부, |x|·2^1074) 로 바꾼다.
fn scaled(x: f64) -> (bool, BigUint) {
    let bits = x.to_bits();
    let neg = bits >> 63 == 1;
    let exp_field = ((bits >> 52) & 0x7ff) as i64;
    let frac = bits & ((1u64 << 52) - 1);
    let (mant, exp) = if exp_field == 0 {
        (frac, -SCALE)
    } else {
        (frac | (1u64 << 52), exp_field - 1075)
    };
    let big = BigUint::from_u128(mant as u128).shl((exp + SCALE) as u64);
    (neg, big)
}

/// Σx·2^1074 (부호, 크기) 와 Σx²·2^2148.
struct Sums {
    neg: bool,
    sum: BigUint,
    sum_sq: BigUint,
}

fn exact_sums(numbers: &[f64]) -> Sums {
    let mut pos = BigUint::zero();
    let mut negs = BigUint::zero();
    let mut sum_sq = BigUint::zero();
    for &x in numbers {
        let (neg, v) = scaled(x);
        sum_sq = sum_sq.add(&v.mul(&v));
        if neg {
            negs = negs.add(&v);
        } else {
            pos = pos.add(&v);
        }
    }
    let (neg, sum) = if pos >= negs {
        (false, pos.sub(&negs))
    } else {
        (true, negs.sub(&pos))
    };
    Sums { neg, sum, sum_sq }
}

/// `statistics.mean`: 정확한 합 / n 을 올바르게 반올림. 모든 값이 유한해야 한다.
pub fn mean(numbers: &[f64]) -> f64 {
    let s = exact_sums(numbers);
    // 몫이 최소 66비트가 되도록 넉넉히 민다.
    let (q, r) = s.sum.shl(130).divrem_small(numbers.len() as u64);
    round_to_f64(s.neg, &q, r != 0, -SCALE - 130)
}

/// `statistics.stdev`: sqrt(ss / (n-1)) 를 올바르게 반올림. 모든 값이 유한해야 한다.
pub fn stdev(numbers: &[f64]) -> f64 {
    let n = numbers.len() as u64;
    let s = exact_sums(numbers);
    // ss/(n-1) = (n·Σx² - (Σx)²) / (n(n-1)) · 2^-2148
    let num = s.sum_sq.mul_small(n).sub(&s.sum.mul(&s.sum));
    if num.is_zero() {
        return 0.0;
    }
    let den = n.checked_mul(n - 1).expect("too many numbers");
    let d = num.bit_length() as i64 - (64 - den.leading_zeros()) as i64;
    // 몫이 2^122 ~ 2^125 범위에 들도록 짝수 비트만큼 민다.
    let mut shift = 124 - d;
    if shift % 2 != 0 {
        shift -= 1;
    }
    let (shifted, mut sticky) = if shift >= 0 {
        (num.shl(shift as u64), false)
    } else {
        num.shr_sticky((-shift) as u64)
    };
    let (q, r) = shifted.divrem_small(den);
    sticky |= r != 0;
    let t = q.to_u128();
    let root = isqrt(t);
    sticky |= root * root != t;
    round_to_f64(false, &BigUint::from_u128(root), sticky, -shift / 2 - SCALE)
}

fn isqrt(t: u128) -> u128 {
    let mut x = (t as f64).sqrt() as u128;
    while x * x > t {
        x -= 1;
    }
    while (x + 1) * (x + 1) <= t {
        x += 1;
    }
    x
}

/// (mag + ε)·2^exp2 를 가장 가까운 f64 로(동점은 짝수). sticky 는 ε>0 (버려진 비트가 있었음) 을 뜻한다.
fn round_to_f64(neg: bool, mag: &BigUint, sticky: bool, exp2: i64) -> f64 {
    let sign = if neg { -1.0 } else { 1.0 };
    let bl = mag.bit_length() as i64;
    if bl == 0 {
        return sign * 0.0;
    }
    // 정확히 64비트짜리 m 으로 맞춘다.
    let (m, sticky, exp2) = if bl > 64 {
        let (v, s) = mag.shr_sticky((bl - 64) as u64);
        (v.to_u128(), sticky || s, exp2 + bl - 64)
    } else {
        (mag.to_u128() << (64 - bl), sticky, exp2 - (64 - bl))
    };
    let lead = exp2 + 63;
    let keep = if lead >= -1022 {
        53
    } else {
        53 - (-1022 - lead)
    };
    let drop = 64 - keep;
    if drop >= 66 {
        return sign * 0.0;
    }
    let kept = m >> drop;
    let rem = m & ((1u128 << drop) - 1);
    let half = 1u128 << (drop - 1);
    let round_up = rem > half || (rem == half && (sticky || kept & 1 == 1));
    let kept = kept + round_up as u128;
    sign * ldexp(kept as f64, exp2 + drop)
}

/// f·2^e. f 는 2^53 이하의 정수이고 결과는 (넘치지 않는 한) 정확히 표현 가능해야 한다.
fn ldexp(mut f: f64, mut e: i64) -> f64 {
    let pow2 = |e: i64| f64::from_bits(((e + 1023) as u64) << 52);
    while e > 1023 {
        f *= pow2(1023);
        e -= 1023;
    }
    if e < -1022 {
        f *= pow2(-1022);
        e += 1022;
    }
    f * pow2(e)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn mean_is_correctly_rounded() {
        assert_eq!(mean(&[1.0, 2.0, 3.0, 4.0, 5.0]), 3.0);
        assert_eq!(mean(&[0.1, 0.2, 0.3]), 0.2);
        assert_eq!(mean(&[1e308, 1e308]), 1e308);
        assert_eq!(mean(&[5e-324, 5e-324, 5e-324]), 5e-324);
        assert_eq!(mean(&[-3.0, 4.5, -0.5, 10.0]), 2.75);
        assert_eq!(mean(&[1.0, 2.0, 2.0]), 5.0 / 3.0);
    }

    #[test]
    fn stdev_is_correctly_rounded() {
        assert_eq!(stdev(&[1.0, 2.0, 3.0, 4.0, 5.0]), 2.5f64.sqrt());
        assert_eq!(stdev(&[2.0, 2.0, 2.0]), 0.0);
        assert_eq!(stdev(&[0.0, 2.0]), 2f64.sqrt());
        assert!(stdev(&[1e308, -1e308]).is_finite());
        let tiny = ldexp(1.0, -1000);
        assert_eq!(stdev(&[0.0, tiny]), 0.5f64.sqrt() * tiny);
        assert!(stdev(&[0.0, 5e-324]) > 0.0);
    }

    #[test]
    fn builtin_sum_uses_compensation() {
        assert_eq!(py_sum(&[0.1; 10]), 1.0);
        assert_eq!(py_sum(&[1e100, 1.0, -1e100]), 1.0);
        assert!(py_sum(&[-0.0, -0.0]).is_sign_positive());
        assert_eq!(py_sum(&[1e308, 1e308]), f64::INFINITY);
    }
}
