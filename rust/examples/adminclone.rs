use std::collections::HashSet;

use adminapi::{new_object::NewObject, query::Query};
use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env())
        .init();

    let args = clap::Command::new("adminclone")
        .arg(clap::arg!(<from> "The origin object identified by it's hostname"))
        .arg(
            clap::arg!(-a <add_attribute> "Adds a value to a multi-attribute field")
                .action(clap::ArgAction::Append),
        )
        .arg(
            clap::arg!(-d <delete_attribute> "Deletes a value from a multi-attribute field")
                .action(clap::ArgAction::Append),
        )
        .arg(
            clap::arg!(-s <set_attribute> "Sets the value for an attribute")
                .action(clap::ArgAction::Append),
        )
        .arg(clap::arg!(-c <clear_attribute> "Clears an attribute").action(clap::ArgAction::Append))
        .get_matches();

    let hostname = args
        .get_one::<String>("from")
        .ok_or(anyhow::anyhow!("Missing from argument"))
        .cloned()?;

    let mut query = Query::builder().filter("hostname", hostname).build();
    query.restrict = HashSet::new(); // We want to get all attributes here
    let mut server = query.request().await?.one()?;
    server.attributes.clear("hostname");
    let servertype = server.get("servertype");
    let mut server = NewObject::from_dataset(server.attributes);
    server.set("servertype", servertype)?;

    for pair in args.get_many::<String>("set_attribute").unwrap_or_default() {
        let Some((name, value)) = pair.split_once("=") else {
            return Err(anyhow::anyhow!("Got attribute set without '=': {pair}"));
        };

        server.set(name.to_string(), value.to_string())?;
    }

    for pair in args.get_many::<String>("add_attribute").unwrap_or_default() {
        let Some((name, value)) = pair.split_once("=") else {
            return Err(anyhow::anyhow!("Got attribute set without '=': {pair}"));
        };

        server.attributes.add(name.to_string(), value.to_string());
    }

    for pair in args
        .get_many::<String>("delete_attribute")
        .unwrap_or_default()
    {
        let Some((name, value)) = pair.split_once("=") else {
            return Err(anyhow::anyhow!("Got attribute set without '=': {pair}"));
        };

        server
            .attributes
            .remove(name.to_string(), value.to_string());
    }

    for name in args
        .get_many::<String>("clear_attribute")
        .unwrap_or_default()
    {
        server.attributes.clear(name.to_string());
    }

    server.commit().await?;

    tracing::info!("Server cloned");

    Ok(())
}
