// NpyWriter.hh - minimal NumPy .npy v1.0 writer for float32 arrays.
// Header-only; used only by the GPU optical path to emit Opticks input-photon
// arrays in the sphoton (N,4,4) layout. No third-party deps.
#ifndef CCB_NPYWRITER_HH
#define CCB_NPYWRITER_HH

#include <cerrno>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace CCB {

inline void write_npy_f32(const std::string& path,
                          const float* data,
                          const std::vector<size_t>& shape) {
  if (shape.empty()) {
    throw std::invalid_argument("NPY shape must contain at least one dimension");
  }

  size_t n = 1;
  for (size_t extent : shape) {
    if (extent != 0 && n > std::numeric_limits<size_t>::max() / extent) {
      throw std::overflow_error("NPY shape product overflows size_t");
    }
    n *= extent;
  }
  if (n > 0 && data == nullptr) {
    throw std::invalid_argument("NPY data pointer is null for a non-empty array");
  }

  std::string dict = "{'descr': '<f4', 'fortran_order': False, 'shape': (";
  for (size_t i = 0; i < shape.size(); ++i) {
    dict += std::to_string(shape[i]);
    dict += (i + 1 < shape.size()) ? ", " : "";
  }
  dict += ",), }";
  // v1.0 layout: 6-byte magic + 2-byte version + 2-byte little-endian
  // header_len + header, padded with spaces and terminated by a newline so the
  // total is a multiple of 64 bytes.
  const size_t pre = 10;
  const size_t total_no_pad = pre + dict.size() + 1;
  const size_t pad = (64 - (total_no_pad % 64)) % 64;
  const std::string header = dict + std::string(pad, ' ') + "\n";
  if (header.size() > std::numeric_limits<uint16_t>::max()) {
    throw std::length_error("NPY v1.0 header exceeds 65535 bytes");
  }
  const uint16_t header_len = static_cast<uint16_t>(header.size());
  const unsigned char header_len_le[2] = {
      static_cast<unsigned char>(header_len & 0xffu),
      static_cast<unsigned char>((header_len >> 8u) & 0xffu)};

  std::ofstream f(path, std::ios::binary | std::ios::trunc);
  if (!f) {
    throw std::runtime_error("cannot open NPY output: " + path + ": " +
                             std::strerror(errno));
  }
  f.write("\x93NUMPY", 6);
  const unsigned char version[2] = {1, 0};
  f.write(reinterpret_cast<const char*>(version), 2);
  f.write(reinterpret_cast<const char*>(header_len_le), 2);
  f.write(header.data(), static_cast<std::streamsize>(header.size()));

  const uint16_t endian_probe = 1;
  const bool host_is_little_endian =
      *reinterpret_cast<const unsigned char*>(&endian_probe) == 1;
  if (host_is_little_endian) {
    f.write(reinterpret_cast<const char*>(data),
            static_cast<std::streamsize>(n * sizeof(float)));
  } else {
    for (size_t i = 0; i < n; ++i) {
      uint32_t bits = 0;
      static_assert(sizeof(bits) == sizeof(data[i]), "float32 size mismatch");
      std::memcpy(&bits, data + i, sizeof(bits));
      const unsigned char bytes[4] = {
          static_cast<unsigned char>(bits & 0xffu),
          static_cast<unsigned char>((bits >> 8u) & 0xffu),
          static_cast<unsigned char>((bits >> 16u) & 0xffu),
          static_cast<unsigned char>((bits >> 24u) & 0xffu)};
      f.write(reinterpret_cast<const char*>(bytes), 4);
    }
  }
  f.flush();
  if (!f) {
    throw std::runtime_error("failed while writing NPY output: " + path);
  }
}

}  // namespace CCB

#endif  // CCB_NPYWRITER_HH
