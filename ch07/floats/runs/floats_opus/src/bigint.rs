//! 부호 없는 큰 정수. `statistics` 모듈이 Fraction 으로 하는 정확한 계산을 흉내 내는 데 필요한 연산만 둔다.

use std::cmp::Ordering;

/// 32비트 limb, 리틀 엔디언. 최상위 limb 은 0 이 아니도록 유지한다.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct BigUint {
    limbs: Vec<u32>,
}

impl BigUint {
    pub fn zero() -> Self {
        BigUint { limbs: Vec::new() }
    }

    pub fn from_u128(mut v: u128) -> Self {
        let mut limbs = Vec::new();
        while v != 0 {
            limbs.push(v as u32);
            v >>= 32;
        }
        BigUint { limbs }
    }

    fn trim(&mut self) {
        while self.limbs.last() == Some(&0) {
            self.limbs.pop();
        }
    }

    pub fn is_zero(&self) -> bool {
        self.limbs.is_empty()
    }

    pub fn bit_length(&self) -> u64 {
        match self.limbs.last() {
            None => 0,
            Some(&top) => (self.limbs.len() as u64 - 1) * 32 + (32 - top.leading_zeros() as u64),
        }
    }

    /// 값이 u128 에 들어갈 때만 호출한다.
    pub fn to_u128(&self) -> u128 {
        assert!(self.limbs.len() <= 4);
        self.limbs
            .iter()
            .rev()
            .fold(0u128, |acc, &l| (acc << 32) | l as u128)
    }

    pub fn add(&self, other: &Self) -> Self {
        let (long, short) = if self.limbs.len() >= other.limbs.len() {
            (self, other)
        } else {
            (other, self)
        };
        let mut limbs = Vec::with_capacity(long.limbs.len() + 1);
        let mut carry = 0u64;
        for (i, &a) in long.limbs.iter().enumerate() {
            let b = short.limbs.get(i).copied().unwrap_or(0);
            let s = a as u64 + b as u64 + carry;
            limbs.push(s as u32);
            carry = s >> 32;
        }
        if carry != 0 {
            limbs.push(carry as u32);
        }
        BigUint { limbs }
    }

    /// self - other. self >= other 이어야 한다.
    pub fn sub(&self, other: &Self) -> Self {
        assert!(*self >= *other);
        let mut limbs = Vec::with_capacity(self.limbs.len());
        let mut borrow = 0i64;
        for (i, &a) in self.limbs.iter().enumerate() {
            let b = other.limbs.get(i).copied().unwrap_or(0);
            let mut d = a as i64 - b as i64 - borrow;
            if d < 0 {
                d += 1 << 32;
                borrow = 1;
            } else {
                borrow = 0;
            }
            limbs.push(d as u32);
        }
        let mut r = BigUint { limbs };
        r.trim();
        r
    }

    pub fn mul(&self, other: &Self) -> Self {
        if self.is_zero() || other.is_zero() {
            return Self::zero();
        }
        let mut limbs = vec![0u32; self.limbs.len() + other.limbs.len()];
        for (i, &a) in self.limbs.iter().enumerate() {
            let mut carry = 0u64;
            for (j, &b) in other.limbs.iter().enumerate() {
                let t = a as u64 * b as u64 + limbs[i + j] as u64 + carry;
                limbs[i + j] = t as u32;
                carry = t >> 32;
            }
            limbs[i + other.limbs.len()] = carry as u32;
        }
        let mut r = BigUint { limbs };
        r.trim();
        r
    }

    pub fn mul_small(&self, m: u64) -> Self {
        self.mul(&Self::from_u128(m as u128))
    }

    /// (몫, 나머지). d 는 0 이 아니어야 한다.
    pub fn divrem_small(&self, d: u64) -> (Self, u64) {
        assert!(d != 0);
        let mut limbs = vec![0u32; self.limbs.len()];
        let mut rem = 0u128;
        for i in (0..self.limbs.len()).rev() {
            let cur = (rem << 32) | self.limbs[i] as u128;
            limbs[i] = (cur / d as u128) as u32;
            rem = cur % d as u128;
        }
        let mut q = BigUint { limbs };
        q.trim();
        (q, rem as u64)
    }

    pub fn shl(&self, bits: u64) -> Self {
        if self.is_zero() {
            return Self::zero();
        }
        let words = (bits / 32) as usize;
        let rem = (bits % 32) as u32;
        let mut limbs = vec![0u32; words];
        if rem == 0 {
            limbs.extend_from_slice(&self.limbs);
        } else {
            let mut carry = 0u32;
            for &l in &self.limbs {
                limbs.push((l << rem) | carry);
                carry = l >> (32 - rem);
            }
            if carry != 0 {
                limbs.push(carry);
            }
        }
        BigUint { limbs }
    }

    /// 오른쪽으로 밀고, 버려진 비트 중 1 이 있었는지도 돌려준다.
    pub fn shr_sticky(&self, bits: u64) -> (Self, bool) {
        let words = (bits / 32) as usize;
        if words >= self.limbs.len() {
            return (Self::zero(), !self.is_zero());
        }
        let rem = (bits % 32) as u32;
        let mut sticky = self.limbs[..words].iter().any(|&l| l != 0);
        let src = &self.limbs[words..];
        let mut limbs = Vec::with_capacity(src.len());
        if rem == 0 {
            limbs.extend_from_slice(src);
        } else {
            sticky |= src[0] & ((1u32 << rem) - 1) != 0;
            for i in 0..src.len() {
                let hi = src.get(i + 1).copied().unwrap_or(0);
                limbs.push((src[i] >> rem) | (hi << (32 - rem)));
            }
        }
        let mut r = BigUint { limbs };
        r.trim();
        (r, sticky)
    }
}

impl PartialOrd for BigUint {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for BigUint {
    fn cmp(&self, other: &Self) -> Ordering {
        self.limbs
            .len()
            .cmp(&other.limbs.len())
            .then_with(|| self.limbs.iter().rev().cmp(other.limbs.iter().rev()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn arithmetic_roundtrip() {
        let a = BigUint::from_u128(0xdead_beef_1234_5678_9abc);
        let b = BigUint::from_u128(0x1_0000_0001);
        let p = a.mul(&b);
        assert_eq!(p.to_u128(), 0xdead_beef_1234_5678_9abc * 0x1_0000_0001);
        let (q, r) = p.divrem_small(0x1_0000_0001);
        assert_eq!((q, r), (a.clone(), 0));
        assert_eq!(a.shl(77).shr_sticky(77), (a.clone(), false));
        assert!(a.shr_sticky(3).1);
        assert_eq!(a.add(&b).sub(&b), a);
        assert_eq!(BigUint::from_u128(1).shl(100).bit_length(), 101);
    }
}
