use adminapi::api::new_object;
use adminapi::filter::*;
use adminapi::query::Query;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    env_logger::init();

    let query = Query::builder()
        .filter("hostname", regexp(".*payment-staging.*"))
        .filter("os", not(empty()))
        .restrict(["hostname", "responsible_admin", "os"])
        .build();

    // The fields are unused, but this example still should show, that you can have the query return structured data
    #[allow(dead_code)]
    #[derive(Clone, Debug, serde::Deserialize)]
    struct MyServer {
        hostname: String,
        os: String,
        responsible_admin: Vec<String>,
    }

    let servers = query.request_typed::<MyServer>().await?;
    for server in servers.into_iter() {
        println!("{server:#?}");
    }

    let obj = new_object("service_group").await?;

    println!("{obj:#?}");

    Ok(())
}
