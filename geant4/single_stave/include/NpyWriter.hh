// NpyWriter.hh - minimal NumPy .npy v1.0 writer for float32 arrays.
// Header-only; used only by the GPU optical path to emit Opticks input-photon
// arrays in the sphoton (N,4,4) layout. No third-party deps.
#ifndef CCB_NPYWRITER_HH
#define CCB_NPYWRITER_HH

#include <fstream>
#include <vector>
#include <cstdint>
#include <string>

namespace CCB {

inline void write_npy_f32(const std::string& path,
                          const float* data,
                          const std::vector<size_t>& shape) {
  std::string dict = "{'descr': '<f4', 'fortran_order': False, 'shape': (";
  for (size_t i = 0; i < shape.size(); ++i) {
    dict += std::to_string(shape[i]);
    dict += (i + 1 < shape.size()) ? ", " : "";
  }
  dict += ",), }";
  // v1.0 layout: 6-byte magic + 2-byte version + 2-byte header_len + header,
  // padded with spaces + a trailing newline so the total is a multiple of 64.
  const size_t pre = 10;                 // magic(6) + ver(2) + len(2)
  const size_t total_no_pad = pre + dict.size() + 1;  // +1 for trailing newline
  const size_t pad = (64 - (total_no_pad % 64)) % 64;
  std::string header = dict + std::string(pad, ' ') + "\n";
  const uint16_t header_len = static_cast<uint16_t>(header.size());

  std::ofstream f(path, std::ios::binary);
  f.write("\x93NUMPY", 6);
  const uint8_t ver[2] = {1, 0};
  f.write(reinterpret_cast<const char*>(ver), 2);
  f.write(reinterpret_cast<const char*>(&header_len), 2);
  f.write(header.data(), static_cast<std::streamsize>(header.size()));
  size_t n = 1;
  for (size_t s : shape) n *= s;
  f.write(reinterpret_cast<const char*>(data),
          static_cast<std::streamsize>(n * sizeof(float)));
}

}  // namespace CCB

#endif  // CCB_NPYWRITER_HH
