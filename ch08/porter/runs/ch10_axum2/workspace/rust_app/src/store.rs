//! 메모리 저장소. id 는 1부터 늘고 다시 쓰지 않는다. BTreeMap 이라 순회 순서가 id 오름차순(= 삽입 순서)

use std::collections::BTreeMap;

use crate::lax::PyInt;
use crate::models::{ItemIn, ItemPatch, Patch};

#[derive(Debug, Clone, PartialEq)]
pub struct Item {
    pub id: u64,
    pub name: String,
    pub price: f64,
    pub quantity: i64,
    pub tags: Vec<String>,
}

pub struct Store {
    items: BTreeMap<u64, Item>,
    next_id: u64,
}

pub enum ReserveOutcome {
    NotFound,
    Insufficient { available: i64 },
    Reserved { remaining: i64 },
}

impl Default for Store {
    fn default() -> Self {
        Store {
            items: BTreeMap::new(),
            next_id: 1,
        }
    }
}

fn key(id: &PyInt) -> Option<u64> {
    id.to_string().parse().ok()
}

impl Store {
    pub fn create(&mut self, body: ItemIn) -> Item {
        let item = Item {
            id: self.next_id,
            name: body.name,
            price: body.price,
            quantity: body.quantity,
            tags: body.tags,
        };
        self.items.insert(item.id, item.clone());
        self.next_id += 1;
        item
    }

    pub fn get(&self, id: &PyInt) -> Option<&Item> {
        self.items.get(&key(id)?)
    }

    /// 태그 조건에 맞는 것 중 offset..offset+limit 와 전체 수
    pub fn list(&self, tag: Option<&str>, offset: usize, limit: usize) -> (Vec<Item>, usize) {
        let matched: Vec<&Item> = self
            .items
            .values()
            .filter(|item| match tag {
                Some(t) => item.tags.iter().any(|x| x == t),
                None => true,
            })
            .collect();
        let page = matched
            .iter()
            .skip(offset)
            .take(limit)
            .map(|item| (*item).clone())
            .collect();
        (page, matched.len())
    }

    pub fn update(&mut self, id: &PyInt, patch: ItemPatch) -> Option<Item> {
        let item = self.items.get_mut(&key(id)?)?;
        if let Patch::Value(name) = patch.name {
            item.name = name;
        }
        if let Patch::Value(price) = patch.price {
            item.price = price;
        }
        if let Patch::Value(quantity) = patch.quantity {
            item.quantity = quantity;
        }
        if let Patch::Value(tags) = patch.tags {
            item.tags = tags;
        }
        Some(item.clone())
    }

    pub fn delete(&mut self, id: &PyInt) -> bool {
        key(id).and_then(|k| self.items.remove(&k)).is_some()
    }

    /// 확인과 차감을 한 번에 한다(호출하는 쪽이 락을 쥔 채로)
    pub fn reserve(&mut self, id: &PyInt, quantity: i64) -> ReserveOutcome {
        let Some(item) = key(id).and_then(|k| self.items.get_mut(&k)) else {
            return ReserveOutcome::NotFound;
        };
        if quantity > item.quantity {
            return ReserveOutcome::Insufficient {
                available: item.quantity,
            };
        }
        item.quantity -= quantity;
        ReserveOutcome::Reserved {
            remaining: item.quantity,
        }
    }

    /// (개수, 수량 합, 가치 합). 가치 합은 항목이 없으면 None(Python 의 정수 0)
    pub fn stats(&self) -> (usize, i64, Option<f64>) {
        let total_quantity = self.items.values().map(|item| item.quantity).sum();
        let values: Vec<f64> = self
            .items
            .values()
            .map(|item| item.price * item.quantity as f64)
            .collect();
        let total_value = (!values.is_empty()).then(|| python_sum(&values));
        (self.items.len(), total_quantity, total_value)
    }
}

/// CPython 3.12 builtin sum() 의 실수 경로(Neumaier 보정 합산)
pub fn python_sum(values: &[f64]) -> f64 {
    let mut total = 0.0;
    let mut c = 0.0;
    for &x in values {
        let t = total + x;
        if f64::abs(total) >= f64::abs(x) {
            c += (total - t) + x;
        } else {
            c += (x - t) + total;
        }
        total = t;
    }
    if c != 0.0 && c.is_finite() {
        total += c;
    }
    total
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sum_is_compensated() {
        assert_eq!(python_sum(&[0.1 * 3.0, 0.2 * 3.0, 0.3 * 3.0]), 1.8);
        assert_eq!(python_sum(&[-0.0]).to_bits(), 0.0f64.to_bits());
    }
}
