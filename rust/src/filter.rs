use std::collections::HashMap;

pub type FilterValue = serde_json::Value;

pub type AttributeFilter = HashMap<String, FilterValue>;

pub trait IntoFilterValue {
    fn into_filter_value(self) -> FilterValue;
}

/// ServerAdmin All Filter
pub fn all(value: impl IntoFilterValue + 'static) -> FilterValue {
    create_filter("All", value)
}

/// ServerAdmin Any Filter
pub fn any(value: impl IntoFilterValue + 'static) -> FilterValue {
    create_filter("Any", value)
}

/// ServerAdmin ContainedBy Filter
pub fn contained_by(value: impl IntoFilterValue + 'static) -> FilterValue {
    create_filter("ContainedBy", value)
}

/// ServerAdmin ContainedOnlyBy Filter
pub fn contained_only_by(value: impl IntoFilterValue + 'static) -> FilterValue {
    create_filter("ContainedOnlyBy", value)
}

/// ServerAdmin Contains Filter
pub fn contains(value: impl IntoFilterValue + 'static) -> FilterValue {
    create_filter("Contains", value)
}

/// ServerAdmin Empty Filter
pub fn empty() -> FilterValue {
    create_filter("Empty", ())
}

/// ServerAdmin GreaterThan Filter
pub fn greater_than(value: impl IntoFilterValue + 'static) -> FilterValue {
    create_filter("GreaterThan", value)
}

/// ServerAdmin GreaterThanOrEquals Filter
pub fn greater_than_or_equals(value: impl IntoFilterValue + 'static) -> FilterValue {
    create_filter("GreaterThanOrEquals", value)
}

/// ServerAdmin LessThan Filter
pub fn less_than(value: impl IntoFilterValue + 'static) -> FilterValue {
    create_filter("LessThan", value)
}

/// ServerAdmin LessThanOrEquals Filter
pub fn less_than_or_equals(value: impl IntoFilterValue + 'static) -> FilterValue {
    create_filter("LessThanOrEquals", value)
}

/// ServerAdmin Not Filter
pub fn not(value: impl IntoFilterValue + 'static) -> FilterValue {
    create_filter("Not", value)
}

/// ServerAdmin Overlaps Filter
pub fn overlaps(value: impl IntoFilterValue + 'static) -> FilterValue {
    create_filter("Overlaps", value)
}

/// ServerAdmin Regexp Filter
pub fn regexp(value: impl IntoFilterValue + 'static) -> FilterValue {
    create_filter("Regexp", value)
}

/// ServerAdmin StartsWith Filter
pub fn starts_with(value: impl IntoFilterValue + 'static) -> FilterValue {
    create_filter("StartsWith", value)
}

impl IntoFilterValue for () {
    fn into_filter_value(self) -> FilterValue {
        FilterValue::Null
    }
}

impl IntoFilterValue for String {
    fn into_filter_value(self) -> FilterValue {
        FilterValue::String(self)
    }
}

impl IntoFilterValue for &str {
    fn into_filter_value(self) -> FilterValue {
        FilterValue::String(self.to_string())
    }
}

impl IntoFilterValue for i32 {
    fn into_filter_value(self) -> FilterValue {
        FilterValue::from(self)
    }
}

impl<T: IntoFilterValue + 'static> IntoFilterValue for Vec<T> {
    fn into_filter_value(self) -> FilterValue {
        FilterValue::from_iter(self.into_iter().map(IntoFilterValue::into_filter_value))
    }
}

impl IntoFilterValue for serde_json::Value {
    fn into_filter_value(self) -> FilterValue {
        self
    }
}

/// Filters on an attribute
fn create_filter(filter_name: impl ToString, value: impl IntoFilterValue + 'static) -> FilterValue {
    let mut filter = HashMap::new();
    filter.insert(filter_name.to_string(), value.into_filter_value());

    FilterValue::from_iter(filter)
}
