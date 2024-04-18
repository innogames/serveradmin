use adminapi::api::{commit_changes, new_object};
use adminapi::commit::Commit;
use adminapi::filter::{empty, not, regexp};
use adminapi::query::Query;

#[tokio::main]
pub async fn main() -> anyhow::Result<()> {
    env_logger::init();
    let mut server = Query::builder()
        .filter("hostname", regexp(".*payment-staging.*"))
        .filter("os", not(empty()))
        .restrict(["hostname", "responsible_admin", "os"])
        .build()
        .request()
        .await?
        .all()
        .pop()
        .ok_or(anyhow::anyhow!("No servers returned"))?;

    server
        .set("os", "bookworm")?
        .add("responsible_admin", "yannik.schwiegerr")?
        .remove("responsible_admin", "yannik.schwieger")?;

    let mut new_sg = new_object("service_group").await?.result;
    new_sg
        .set("hostname", "yannik-adminapi-rs-2.test.sg")
        .set("project", "test")
        .add("responsible_admin", "yannik.schwieger")
        .add("protocol_ports_inbound", "tcp443");

    let changes = Commit::new().update(server.changeset()).create(new_sg);
    println!("{}", serde_json::to_string_pretty(&changes)?);

    let response = commit_changes(&changes).await?;
    println!("{response:#?}");

    Ok(())
}
