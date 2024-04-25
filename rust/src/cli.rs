use std::str::Chars;

use crate::filter::{AttributeFilter, FilterValue, IntoFilterValue};
use crate::filter;

pub fn parse_filter_args(args: impl Iterator<Item=String> + 'static) -> anyhow::Result<AttributeFilter> {
    let mut filter = AttributeFilter::default();

    for arg in args {
        let mut split = arg.split('=');
        let Some(attribute) = split.next() else {
            continue;
        };
        let tail = split.collect::<String>();
        if tail.is_empty() {
            return Err(anyhow::anyhow!("Attribute value is missing"));
        }

        filter.insert(attribute.to_string(), parse_filter_arg(tail));
    }

    Ok(filter)
}

pub fn parse_filter_arg(arg: String) -> FilterValue {
    let mut chars = arg.chars();

    lookup_function(&mut chars)
}

pub fn lookup_function(chars: &mut Chars) -> FilterValue {
    let mut buffer = String::new();
    let mut fn_name = String::new();
    let mut depth = 0;
    let mut inner = Vec::new();

    for char in chars.by_ref() {
        if char == '(' {
            depth += 1;
        }
        if char == ')' {
            depth -= 1;
        }

        if char == '(' && depth == 1 {
            fn_name.extend(buffer.drain(0..));
        }


        if char == '(' && depth == 1 {
            continue;
        }

        if char == ')' && depth == 0 {
            continue;
        }

        if depth == 0 && char == ' ' {
            inner.push(buffer.clone());
            buffer.clear();

            continue;
        }

        buffer.push(char);
    }

    if fn_name.is_empty() && inner.is_empty() {
        return buffer.into_filter_value();
    }

    if !buffer.is_empty() {
        inner.push(buffer);
    }

    let filter_fn = get_filter_function(&fn_name.to_lowercase());
    let mut inner_filters = inner.into_iter().map(|filter| {
        let mut chars = filter.chars();

        lookup_function(&mut chars)
    }).collect::<Vec<_>>();

    if inner_filters.len() == 1 {
        filter_fn(inner_filters.pop().unwrap())
    } else {
        filter_fn(FilterValue::Array(inner_filters))
    }
}

fn get_filter_function(name: &str) -> Box<dyn Fn(FilterValue) -> FilterValue> {
    match name {
        "all" => {
            Box::new(filter::all)
        }
        "any" => {
            Box::new(filter::any)
        }
        "containedby" => {
            Box::new(filter::contained_by)
        }
        "containedonlyby" => {
            Box::new(filter::contained_only_by)
        }
        "contains" => {
            Box::new(filter::contains)
        }
        "empty" => {
            Box::new(|_| filter::empty())
        }
        "greaterthan" => {
            Box::new(filter::greater_than)
        }
        "greaterthanorequals" => {
            Box::new(filter::greater_than_or_equals)
        }
        "lessthan" => {
            Box::new(filter::less_than)
        }
        "lessthanorequals" => {
            Box::new(filter::less_than_or_equals)
        }
        "not" => {
            Box::new(filter::not)
        }
        "overlaps" => {
            Box::new(filter::overlaps)
        }
        "regexp" => {
            Box::new(filter::regexp)
        }
        "startswith" => {
            Box::new(filter::starts_with)
        }
        _name => {
            Box::new(IntoFilterValue::into_filter_value)
        }
    }
}
