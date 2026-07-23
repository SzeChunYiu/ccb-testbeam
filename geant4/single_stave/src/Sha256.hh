// Sha256.hh — Self-contained SHA-256 (FIPS 180-4) for CCB single-stave.
// Public-domain style: no external dependencies. Used for a deterministic
// geometry+config digest replacing the non-cryptographic std::hash.
#ifndef CCB_SHA256_HH
#define CCB_SHA256_HH

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>

class Sha256 {
 public:
  Sha256();

  // Feed data into the hash. May be called multiple times.
  void update(const std::uint8_t* data, std::size_t len);
  void update(const std::string& s);

  // Finalize and return the 32-byte raw digest.
  std::array<std::uint8_t, 32> digest();

  // --- Convenience statics ---
  // Hash a string in one shot, returning the raw digest.
  static std::array<std::uint8_t, 32> compute(const std::string& s);
  // Lowercase hex encoding of a raw digest (64 chars).
  static std::string hex(const std::array<std::uint8_t, 32>& d);
  // Hash + hex in one call (64-char lowercase string).
  static std::string hex(const std::string& s);

 private:
  std::uint32_t state_[8];
  std::uint64_t bitlen_;
  std::uint32_t buflen_;
  std::uint8_t  buffer_[64];

  void transform(const std::uint8_t* block);
};

#endif  // CCB_SHA256_HH
