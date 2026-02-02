//! Hybrid Encryption using ML-KEM + AES-256-GCM
//! 
//! Combines post-quantum key encapsulation with symmetric encryption
//! for secure data encryption at rest and in transit.

use aes_gcm::{
    aead::{Aead, KeyInit, OsRng},
    Aes256Gcm, Nonce,
};
use hkdf::Hkdf;
use sha2::Sha256;
use rand::RngCore;
use serde::{Deserialize, Serialize};
use crate::error::CryptoError;
use crate::kem;

/// Nonce size for AES-256-GCM (96 bits)
const NONCE_SIZE: usize = 12;

/// HKDF info string for key derivation
const HKDF_INFO: &[u8] = b"quantum-safe-aes-key-v1";

/// Salt for HKDF (using a fixed salt for deterministic derivation)
const HKDF_SALT: &[u8] = b"ML-KEM-768+AES-256-GCM";

/// Encrypted data envelope with PQC-wrapped key
#[derive(Clone, Serialize, Deserialize)]
pub struct EncryptedEnvelope {
    /// ML-KEM encapsulated ciphertext (contains wrapped symmetric key)
    pub kem_ciphertext: Vec<u8>,
    /// AES-256-GCM nonce
    pub nonce: Vec<u8>,
    /// AES-256-GCM encrypted data
    pub ciphertext: Vec<u8>,
    /// Algorithm identifier
    pub algorithm: String,
}

impl EncryptedEnvelope {
    /// Export as base64 JSON
    pub fn to_base64_json(&self) -> Result<String, CryptoError> {
        use base64::Engine;
        let json = serde_json::to_vec(self)
            .map_err(|_| CryptoError::SerializationError)?;
        Ok(base64::engine::general_purpose::STANDARD.encode(&json))
    }

    /// Import from base64 JSON
    pub fn from_base64_json(encoded: &str) -> Result<Self, CryptoError> {
        use base64::Engine;
        let json = base64::engine::general_purpose::STANDARD
            .decode(encoded)
            .map_err(|_| CryptoError::InvalidCiphertext)?;
        serde_json::from_slice(&json)
            .map_err(|_| CryptoError::SerializationError)
    }
}

/// Encrypt data using hybrid ML-KEM + AES-256-GCM
/// 
/// # Arguments
/// * `plaintext` - Data to encrypt
/// * `recipient_public_key` - Recipient's ML-KEM public key
/// 
/// # Returns
/// * `EncryptedEnvelope` containing all components needed for decryption
pub fn encrypt(plaintext: &[u8], recipient_public_key: &[u8]) -> Result<EncryptedEnvelope, CryptoError> {
    // Step 1: Encapsulate to get shared secret
    let encap_result = kem::encapsulate(recipient_public_key)?;
    
    // Step 2: Derive AES key from shared secret (first 32 bytes)
    let aes_key = derive_aes_key(&encap_result.shared_secret)?;
    
    // Step 3: Generate random nonce
    let mut nonce_bytes = [0u8; NONCE_SIZE];
    OsRng.fill_bytes(&mut nonce_bytes);
    let nonce = Nonce::from_slice(&nonce_bytes);
    
    // Step 4: Encrypt with AES-256-GCM
    let cipher = Aes256Gcm::new_from_slice(&aes_key)
        .map_err(|_| CryptoError::EncryptionFailed)?;
    let ciphertext = cipher
        .encrypt(nonce, plaintext)
        .map_err(|_| CryptoError::EncryptionFailed)?;
    
    Ok(EncryptedEnvelope {
        kem_ciphertext: encap_result.ciphertext,
        nonce: nonce_bytes.to_vec(),
        ciphertext,
        algorithm: "ML-KEM-768+AES-256-GCM".to_string(),
    })
}

/// Decrypt data using hybrid ML-KEM + AES-256-GCM
/// 
/// # Arguments
/// * `envelope` - Encrypted envelope from `encrypt()`
/// * `recipient_secret_key` - Recipient's ML-KEM secret key
/// 
/// # Returns
/// * Decrypted plaintext bytes
pub fn decrypt(envelope: &EncryptedEnvelope, recipient_secret_key: &[u8]) -> Result<Vec<u8>, CryptoError> {
    // Step 1: Decapsulate to recover shared secret
    let shared_secret = kem::decapsulate(&envelope.kem_ciphertext, recipient_secret_key)?;
    
    // Step 2: Derive AES key from shared secret
    let aes_key = derive_aes_key(&shared_secret)?;
    
    // Step 3: Decrypt with AES-256-GCM
    let nonce = Nonce::from_slice(&envelope.nonce);
    let cipher = Aes256Gcm::new_from_slice(&aes_key)
        .map_err(|_| CryptoError::DecryptionFailed)?;
    let plaintext = cipher
        .decrypt(nonce, envelope.ciphertext.as_ref())
        .map_err(|_| CryptoError::DecryptionFailed)?;
    
    Ok(plaintext)
}

/// Encrypt with base64 encoded public key
pub fn encrypt_base64(plaintext: &[u8], recipient_public_key_b64: &str) -> Result<EncryptedEnvelope, CryptoError> {
    use base64::Engine;
    let public_key = base64::engine::general_purpose::STANDARD
        .decode(recipient_public_key_b64)
        .map_err(|_| CryptoError::InvalidKeyFormat)?;
    encrypt(plaintext, &public_key)
}

/// Decrypt with base64 encoded secret key
pub fn decrypt_base64(envelope: &EncryptedEnvelope, recipient_secret_key_b64: &str) -> Result<Vec<u8>, CryptoError> {
    use base64::Engine;
    let secret_key = base64::engine::general_purpose::STANDARD
        .decode(recipient_secret_key_b64)
        .map_err(|_| CryptoError::InvalidKeyFormat)?;
    decrypt(envelope, &secret_key)
}

/// Encrypt a JSON-serializable object
pub fn encrypt_json<T: Serialize>(data: &T, recipient_public_key: &[u8]) -> Result<EncryptedEnvelope, CryptoError> {
    let json_bytes = serde_json::to_vec(data)
        .map_err(|_| CryptoError::SerializationError)?;
    encrypt(&json_bytes, recipient_public_key)
}

/// Decrypt to a JSON-deserializable object
pub fn decrypt_json<T: for<'de> Deserialize<'de>>(
    envelope: &EncryptedEnvelope,
    recipient_secret_key: &[u8],
) -> Result<T, CryptoError> {
    let plaintext = decrypt(envelope, recipient_secret_key)?;
    serde_json::from_slice(&plaintext)
        .map_err(|_| CryptoError::SerializationError)
}

/// Derive AES-256 key from ML-KEM shared secret using HKDF-SHA256
/// 
/// Uses HKDF (HMAC-based Key Derivation Function) as per RFC 5869
/// for secure key derivation from the ML-KEM shared secret.
fn derive_aes_key(shared_secret: &[u8]) -> Result<[u8; 32], CryptoError> {
    if shared_secret.len() < 32 {
        return Err(CryptoError::InvalidKeyLength);
    }
    
    // Use HKDF-SHA256 for key derivation
    let hk = Hkdf::<Sha256>::new(Some(HKDF_SALT), shared_secret);
    let mut aes_key = [0u8; 32];
    hk.expand(HKDF_INFO, &mut aes_key)
        .map_err(|_| CryptoError::KeyDerivationFailed)?;
    
    Ok(aes_key)
}

/// Derive AES-256 key with additional context for domain separation
/// 
/// Allows specifying additional context info for different use cases
/// (e.g., different keys for encryption vs. MAC)
#[allow(dead_code)]
fn derive_aes_key_with_context(shared_secret: &[u8], context: &[u8]) -> Result<[u8; 32], CryptoError> {
    if shared_secret.len() < 32 {
        return Err(CryptoError::InvalidKeyLength);
    }
    
    // Combine standard info with context
    let mut info = HKDF_INFO.to_vec();
    info.extend_from_slice(b":");
    info.extend_from_slice(context);
    
    let hk = Hkdf::<Sha256>::new(Some(HKDF_SALT), shared_secret);
    let mut aes_key = [0u8; 32];
    hk.expand(&info, &mut aes_key)
        .map_err(|_| CryptoError::KeyDerivationFailed)?;
    
    Ok(aes_key)
}

/// Sealed box: encrypt with signature for authenticated encryption
#[derive(Clone, Serialize, Deserialize)]
pub struct SignedEncryptedEnvelope {
    pub envelope: EncryptedEnvelope,
    pub signature: Vec<u8>,
    pub signer_public_key: Vec<u8>,
}

impl SignedEncryptedEnvelope {
    /// Create a signed encrypted envelope
    pub fn create(
        plaintext: &[u8],
        recipient_public_key: &[u8],
        signer_secret_key: &[u8],
        signer_public_key: &[u8],
    ) -> Result<Self, CryptoError> {
        // Encrypt the data
        let envelope = encrypt(plaintext, recipient_public_key)?;
        
        // Sign the envelope
        let envelope_bytes = serde_json::to_vec(&envelope)
            .map_err(|_| CryptoError::SerializationError)?;
        let signature = crate::signatures::sign(&envelope_bytes, signer_secret_key)?;
        
        Ok(SignedEncryptedEnvelope {
            envelope,
            signature,
            signer_public_key: signer_public_key.to_vec(),
        })
    }

    /// Verify signature and decrypt
    pub fn open(&self, recipient_secret_key: &[u8]) -> Result<Vec<u8>, CryptoError> {
        // Verify the signature
        let envelope_bytes = serde_json::to_vec(&self.envelope)
            .map_err(|_| CryptoError::SerializationError)?;
        let is_valid = crate::signatures::verify(
            &envelope_bytes,
            &self.signature,
            &self.signer_public_key,
        )?;
        
        if !is_valid {
            return Err(CryptoError::InvalidSignature);
        }
        
        // Decrypt the data
        decrypt(&self.envelope, recipient_secret_key)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::kem::KemKeyPair;
    use crate::signatures::SigningKeyPair;

    #[test]
    fn test_encrypt_decrypt_roundtrip() {
        let keypair = KemKeyPair::generate().unwrap();
        let plaintext = b"Secret quantum optimization data!";
        
        let envelope = encrypt(plaintext, &keypair.public_key).unwrap();
        let decrypted = decrypt(&envelope, &keypair.secret_key).unwrap();
        
        assert_eq!(plaintext.to_vec(), decrypted);
    }

    #[test]
    fn test_encrypt_decrypt_json() {
        #[derive(Serialize, Deserialize, Debug, PartialEq)]
        struct TestData {
            value: i32,
            name: String,
        }
        
        let keypair = KemKeyPair::generate().unwrap();
        let data = TestData {
            value: 42,
            name: "quantum".to_string(),
        };
        
        let envelope = encrypt_json(&data, &keypair.public_key).unwrap();
        let decrypted: TestData = decrypt_json(&envelope, &keypair.secret_key).unwrap();
        
        assert_eq!(data, decrypted);
    }

    #[test]
    fn test_signed_encrypted_envelope() {
        let recipient_kem = KemKeyPair::generate().unwrap();
        let signer = SigningKeyPair::generate().unwrap();
        let plaintext = b"Authenticated and encrypted data";
        
        let signed_envelope = SignedEncryptedEnvelope::create(
            plaintext,
            &recipient_kem.public_key,
            &signer.secret_key,
            &signer.public_key,
        ).unwrap();
        
        let decrypted = signed_envelope.open(&recipient_kem.secret_key).unwrap();
        
        assert_eq!(plaintext.to_vec(), decrypted);
    }

    #[test]
    fn test_tampered_envelope_fails() {
        let recipient_kem = KemKeyPair::generate().unwrap();
        let signer = SigningKeyPair::generate().unwrap();
        let plaintext = b"Original data";
        
        let mut signed_envelope = SignedEncryptedEnvelope::create(
            plaintext,
            &recipient_kem.public_key,
            &signer.secret_key,
            &signer.public_key,
        ).unwrap();
        
        // Tamper with the ciphertext
        signed_envelope.envelope.ciphertext[0] ^= 0xff;
        
        // Should fail verification or decryption
        let result = signed_envelope.open(&recipient_kem.secret_key);
        assert!(result.is_err());
    }
}
