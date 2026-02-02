//! Error types for the quantum-safe cryptography module

use thiserror::Error;

/// Cryptography errors
#[derive(Error, Debug)]
pub enum CryptoError {
    #[error("Invalid public key format")]
    InvalidPublicKey,

    #[error("Invalid secret key format")]
    InvalidSecretKey,

    #[error("Invalid key format or encoding")]
    InvalidKeyFormat,

    #[error("Invalid key length")]
    InvalidKeyLength,

    #[error("Invalid ciphertext")]
    InvalidCiphertext,

    #[error("Invalid signature")]
    InvalidSignature,

    #[error("Encryption failed")]
    EncryptionFailed,

    #[error("Decryption failed")]
    DecryptionFailed,

    #[error("Serialization/deserialization error")]
    SerializationError,

    #[error("Unsupported security level")]
    UnsupportedSecurityLevel,

    #[error("Key generation failed")]
    KeyGenerationFailed,

    #[error("Key derivation failed")]
    KeyDerivationFailed,

    #[error("Random number generation failed")]
    RngFailed,
}
