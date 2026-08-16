// Sha256.cc — Self-contained SHA-256 (FIPS 180-4) implementation.
// Public-domain style; no OpenSSL or external dependency.
#include "Sha256.hh"

#include <cstring>

namespace {

// Round constants (first 32 bits of the fractional parts of the cube
// roots of the first 64 primes).
constexpr std::uint32_t K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
    0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
    0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
    0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
    0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};

inline std::uint32_t rotr(std::uint32_t x, int n) {
  return (x >> n) | (x << (32 - n));
}

inline std::uint32_t load_be32(const std::uint8_t* p) {
  return (static_cast<std::uint32_t>(p[0]) << 24) |
         (static_cast<std::uint32_t>(p[1]) << 16) |
         (static_cast<std::uint32_t>(p[2]) << 8) |
         static_cast<std::uint32_t>(p[3]);
}

inline void store_be32(std::uint32_t v, std::uint8_t* p) {
  p[0] = static_cast<std::uint8_t>(v >> 24);
  p[1] = static_cast<std::uint8_t>(v >> 16);
  p[2] = static_cast<std::uint8_t>(v >> 8);
  p[3] = static_cast<std::uint8_t>(v);
}

}  // namespace

Sha256::Sha256() : bitlen_(0), buflen_(0) {
  state_[0] = 0x6a09e667;
  state_[1] = 0xbb67ae85;
  state_[2] = 0x3c6ef372;
  state_[3] = 0xa54ff53a;
  state_[4] = 0x510e527f;
  state_[5] = 0x9b05688c;
  state_[6] = 0x1f83d9ab;
  state_[7] = 0x5be0cd19;
}

void Sha256::transform(const std::uint8_t* block) {
  std::uint32_t w[64];
  for (int i = 0; i < 16; ++i) w[i] = load_be32(block + i * 4);
  for (int i = 16; i < 64; ++i) {
    std::uint32_t s0 =
        rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
    std::uint32_t s1 =
        rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
    w[i] = w[i - 16] + s0 + w[i - 7] + s1;
  }

  std::uint32_t a = state_[0], b = state_[1], c = state_[2], d = state_[3];
  std::uint32_t e = state_[4], f = state_[5], g = state_[6], h = state_[7];

  for (int i = 0; i < 64; ++i) {
    std::uint32_t S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
    std::uint32_t ch = (e & f) ^ (~e & g);
    std::uint32_t t1 = h + S1 + ch + K[i] + w[i];
    std::uint32_t S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
    std::uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
    std::uint32_t t2 = S0 + maj;
    h = g;
    g = f;
    f = e;
    e = d + t1;
    d = c;
    c = b;
    b = a;
    a = t1 + t2;
  }

  state_[0] += a;
  state_[1] += b;
  state_[2] += c;
  state_[3] += d;
  state_[4] += e;
  state_[5] += f;
  state_[6] += g;
  state_[7] += h;
}

void Sha256::update(const std::uint8_t* data, std::size_t len) {
  bitlen_ += static_cast<std::uint64_t>(len) * 8;
  while (len > 0) {
    std::size_t copy = 64 - buflen_;
    if (copy > len) copy = len;
    std::memcpy(buffer_ + buflen_, data, copy);
    buflen_ += static_cast<std::uint32_t>(copy);
    data += copy;
    len -= copy;
    if (buflen_ == 64) {
      transform(buffer_);
      buflen_ = 0;
    }
  }
}

void Sha256::update(const std::string& s) {
  update(reinterpret_cast<const std::uint8_t*>(s.data()), s.size());
}

std::array<std::uint8_t, 32> Sha256::digest() {
  // Save the pre-padding bit length (update() below would corrupt it).
  const std::uint64_t bitlen = bitlen_;

  // Append the 0x80 terminator byte.
  buffer_[buflen_++] = 0x80;

  // If there is not enough room for the 8-byte length field in this block,
  // zero-fill to the end, process it, and start a fresh block.
  if (buflen_ > 56) {
    while (buflen_ < 64) buffer_[buflen_++] = 0;
    transform(buffer_);
    buflen_ = 0;
  }

  // Zero-pad until byte 56.
  while (buflen_ < 56) buffer_[buflen_++] = 0;

  // Append the 64-bit big-endian original message length in bits.
  for (int i = 7; i >= 0; --i)
    buffer_[buflen_++] = static_cast<std::uint8_t>(bitlen >> (i * 8));

  transform(buffer_);

  std::array<std::uint8_t, 32> result{};
  for (int i = 0; i < 8; ++i) store_be32(state_[i], result.data() + i * 4);
  return result;
}

std::array<std::uint8_t, 32> Sha256::compute(const std::string& s) {
  Sha256 h;
  h.update(s);
  return h.digest();
}

std::string Sha256::hex(const std::array<std::uint8_t, 32>& d) {
  static const char hexchars[] = "0123456789abcdef";
  std::string s;
  s.reserve(64);
  for (auto b : d) {
    s.push_back(hexchars[b >> 4]);
    s.push_back(hexchars[b & 0x0f]);
  }
  return s;
}

std::string Sha256::hex(const std::string& s) { return hex(compute(s)); }
