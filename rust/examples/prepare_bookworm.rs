use adminapi::cli::parse_filter_args;
use adminapi::commit::AttributeValue;
use adminapi::query::Query;

#[tokio::main]
pub async fn main() -> anyhow::Result<()> {
    let clap = clap::Command::new("prepare_bookworm")
        .arg(clap::arg!([QUERY]).action(clap::ArgAction::Append).help("Query for the preparation").value_parser(clap::value_parser!(String)).num_args(1..).required(true))
        .arg(clap::arg!(--"puppet-environment" <ENVIRONMENT> "Sets an optional puppet environment").value_parser(clap::value_parser!(String)).required(false))
        .arg(clap::arg!(--"maintenance" "Sets the servers to maintenance").action(clap::ArgAction::SetTrue).required(false));

    let matches = clap.get_matches();
    let query = matches.get_many::<String>("QUERY").unwrap().cloned().collect::<Vec<_>>();
    let filters = parse_filter_args(query.into_iter())?;

    let query = Query::builder()
        .filters(filters)
        .restrict(["os", "repositories", "puppet_environment", "state"])
        .build();
    let response = query.request().await?;
    let mut updates = vec![];

    for mut server in response.all() {
        let AttributeValue::String(base_os) = server.get("os") else {
            return Err(anyhow::anyhow!("Unexpected value for os"));
        };

        server.set("os", "bookworm")?;
        let AttributeValue::Array(repos) = server.get("repositories") else {
            return Err(anyhow::anyhow!("Unexpected value for repositories"));
        };

        for repo in repos {
            let AttributeValue::String(repo) = repo else {
                return Err(anyhow::anyhow!("Unexpected value for repository"));
            };

            if !repo.contains(&base_os) {
                continue;
            }

            server.add("repositories", repo.replace(&base_os, "bookworm"))?;
            server.remove("repositories", repo)?;

            if matches.get_flag("maintenance") {
                server.set("state", "maintenance")?;
            }

            if let Some(environment) = matches.get_one::<String>("puppet-environment") {
                if !server.get("puppet_environment").is_null() {
                    return Err(anyhow::anyhow!("Puppet environment is already set. Aborting!"));
                }

                server.set("puppet_environment", environment.clone())?;
            }
        }

        updates.push(async move { server.commit().await });
    }

    futures::future::try_join_all(updates).await?;

    Ok(())
}
