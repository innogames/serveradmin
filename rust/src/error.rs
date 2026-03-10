#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("Missing required attribute: {0}")]
    RequiredAttributeMissing(String),
    #[error("No value was provided for attribute: {0}")]
    MissingValueForAttribute(String),
    #[error("Response expected one result, got {0}")]
    TooManyItems(usize),
    #[error("Got not enough items, expected at least {0}")]
    NotEnoughItems(usize),
    #[error("Unsupported operation on attribute {0}: {1}")]
    UnsupportedOperation(String, &'static str),
    #[error("Got error from serveradmin: {0}")]
    UnknownServerAdminError(String),

    #[error("Unknown error while sending a request: {0}")]
    UnknownRequestError(#[from] reqwest::Error),
    #[error("Unknown error while getting time: {0}")]
    UnknownTimeError(#[from] std::time::SystemTimeError),
    #[error("Error while handling JSON data: {0}")]
    JsonError(#[from] serde_json::Error),
    #[error("Error while handling SSH key: {0}")]
    SshKeyError(#[from] ssh_key::Error),
    #[error("Error while communicating with ssh agent: {0}")]
    SshAgentError(#[from] ssh_agent_client_rs::Error),
    #[error("Error while signing message: {0}")]
    SignatureError(#[from] signature::Error),
    #[error("Error while encoding message: {0}")]
    EncodingError(#[from] ssh_encoding::Error),
    #[error("Error while encoding message: {0}")]
    Base64Error(#[from] ssh_encoding::base64::Error),
    #[error("Error while getting environment variable: {0}")]
    VarError(#[from] std::env::VarError),
    #[error("Unable to extract public key from string: {0}")]
    PublicKeyFormatError(String),
}

pub type Result<T> = std::result::Result<T, Error>;
