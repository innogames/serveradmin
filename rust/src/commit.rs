use std::collections::HashMap;

use serde_json::Number;

pub type AttributeValue = serde_json::Value;

#[derive(Clone, Debug, Default, serde::Deserialize, serde::Serialize)]
pub struct Dataset(HashMap<String, AttributeValue>);

#[derive(Clone, Debug, serde::Deserialize, serde::Serialize)]
#[serde(tag = "action", rename_all = "snake_case")]
pub enum AttributeChange {
    Update {
        old: AttributeValue,
        new: AttributeValue,
    },
    Multi {
        remove: Vec<AttributeValue>,
        add: Vec<AttributeValue>,
    },
}

#[derive(Clone, Debug, Default, serde::Deserialize, serde::Serialize)]
pub struct Changeset {
    pub object_id: u64,
    #[serde(flatten)]
    pub attributes: HashMap<String, AttributeChange>,
}

#[derive(Clone, Debug, Default, serde::Deserialize, serde::Serialize)]
pub struct Commit {
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub created: Vec<Dataset>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub changed: Vec<Changeset>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub deleted: Vec<u64>,
}

pub trait IntoDataset {
    fn into_dataset(self) -> Dataset;
}

pub trait IntoAttributeValue {
    fn into_attribute_value(self) -> AttributeValue;
}

impl Commit {
    pub fn new() -> Self {
        Self {
            created: Default::default(),
            changed: Default::default(),
            deleted: Default::default(),
        }
    }

    pub fn create(mut self, attrs: impl IntoDataset + 'static) -> Self {
        self.created.push(attrs.into_dataset());

        self
    }

    pub fn update(mut self, changeset: Changeset) -> Self {
        self.changed.push(changeset);

        self
    }

    pub fn delete(mut self, object_id: u64) -> Self {
        self.deleted.push(object_id);

        self
    }
}

impl IntoDataset for Dataset {
    fn into_dataset(self) -> Dataset {
        self
    }
}

impl IntoAttributeValue for String {
    fn into_attribute_value(self) -> AttributeValue {
        AttributeValue::String(self)
    }
}

impl IntoAttributeValue for () {
    fn into_attribute_value(self) -> AttributeValue {
        AttributeValue::Null
    }
}

impl IntoAttributeValue for f32 {
    fn into_attribute_value(self) -> AttributeValue {
        AttributeValue::from(self)
    }
}

impl IntoAttributeValue for i32 {
    fn into_attribute_value(self) -> AttributeValue {
        AttributeValue::Number(Number::from(self))
    }
}

impl<T: IntoAttributeValue> IntoAttributeValue for Vec<T> {
    fn into_attribute_value(self) -> AttributeValue {
        AttributeValue::from_iter(
            self.into_iter()
                .map(IntoAttributeValue::into_attribute_value),
        )
    }
}

impl IntoAttributeValue for AttributeValue {
    fn into_attribute_value(self) -> AttributeValue {
        self
    }
}

impl IntoAttributeValue for &str {
    fn into_attribute_value(self) -> AttributeValue {
        AttributeValue::String(self.to_string())
    }
}

impl Dataset {
    pub fn new() -> Self {
        Self(Default::default())
    }

    pub fn set(
        &mut self,
        name: impl ToString,
        attr: impl IntoAttributeValue + 'static,
    ) -> &mut Self {
        self.0.insert(name.to_string(), attr.into_attribute_value());

        self
    }

    pub fn add(
        &mut self,
        name: impl ToString,
        attr: impl IntoAttributeValue + 'static,
    ) -> &mut Self {
        let name = name.to_string();
        let attr = attr.into_attribute_value();

        let value = self.0.entry(name).or_insert(AttributeValue::Array(vec![]));
        if let serde_json::Value::Array(array) = value {
            array.push(attr);
        }

        self
    }

    pub fn remove(
        &mut self,
        name: impl ToString,
        attr: impl IntoAttributeValue + 'static,
    ) -> &mut Self {
        let name = name.to_string();
        let attr = attr.into_attribute_value();

        let Some(AttributeValue::Array(value)) = self.0.get_mut(&name) else {
            return self;
        };

        if let Some(index) = value.iter().position(|val| val == &attr) {
            value.remove(index);
        }

        if value.is_empty() {
            self.0.remove(&name);
        }

        self
    }

    pub fn get(&self, name: &str) -> AttributeValue {
        self.0.get(name).cloned().unwrap_or(AttributeValue::Null)
    }
}
