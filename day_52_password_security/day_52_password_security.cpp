#include <algorithm>
#include <array>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

class Sha256 {
private:
    static constexpr std::array<uint32_t, 64> K = {
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
        0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
        0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
        0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
        0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
        0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
        0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
        0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
        0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
    };

    static uint32_t rotr(uint32_t x, uint32_t n) {
        return (x >> n) | (x << (32 - n));
    }

    static uint32_t ch(uint32_t x, uint32_t y, uint32_t z) {
        return (x & y) ^ (~x & z);
    }

    static uint32_t maj(uint32_t x, uint32_t y, uint32_t z) {
        return (x & y) ^ (x & z) ^ (y & z);
    }

    static uint32_t bigSigma0(uint32_t x) {
        return rotr(x, 2) ^ rotr(x, 13) ^ rotr(x, 22);
    }

    static uint32_t bigSigma1(uint32_t x) {
        return rotr(x, 6) ^ rotr(x, 11) ^ rotr(x, 25);
    }

    static uint32_t smallSigma0(uint32_t x) {
        return rotr(x, 7) ^ rotr(x, 18) ^ (x >> 3);
    }

    static uint32_t smallSigma1(uint32_t x) {
        return rotr(x, 17) ^ rotr(x, 19) ^ (x >> 10);
    }

public:
    static std::array<uint8_t, 32> hash(
        const std::vector<uint8_t>& input
    ) {
        std::vector<uint8_t> data = input;
        const uint64_t bitLength = static_cast<uint64_t>(data.size()) * 8;

        data.push_back(0x80);

        while ((data.size() % 64) != 56) {
            data.push_back(0);
        }

        for (int i = 7; i >= 0; --i) {
            data.push_back(
                static_cast<uint8_t>((bitLength >> (i * 8)) & 0xff)
            );
        }

        std::array<uint32_t, 8> h = {
            0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
            0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
        };

        for (size_t offset = 0; offset < data.size(); offset += 64) {
            std::array<uint32_t, 64> w{};

            for (int i = 0; i < 16; ++i) {
                const size_t p = offset + i * 4;
                w[i] =
                    (static_cast<uint32_t>(data[p]) << 24) |
                    (static_cast<uint32_t>(data[p + 1]) << 16) |
                    (static_cast<uint32_t>(data[p + 2]) << 8) |
                    static_cast<uint32_t>(data[p + 3]);
            }

            for (int i = 16; i < 64; ++i) {
                w[i] = smallSigma1(w[i - 2]) +
                       w[i - 7] +
                       smallSigma0(w[i - 15]) +
                       w[i - 16];
            }

            uint32_t a = h[0];
            uint32_t b = h[1];
            uint32_t c = h[2];
            uint32_t d = h[3];
            uint32_t e = h[4];
            uint32_t f = h[5];
            uint32_t g = h[6];
            uint32_t hh = h[7];

            for (int i = 0; i < 64; ++i) {
                const uint32_t t1 =
                    hh + bigSigma1(e) + ch(e, f, g) + K[i] + w[i];

                const uint32_t t2 =
                    bigSigma0(a) + maj(a, b, c);

                hh = g;
                g = f;
                f = e;
                e = d + t1;
                d = c;
                c = b;
                b = a;
                a = t1 + t2;
            }

            h[0] += a;
            h[1] += b;
            h[2] += c;
            h[3] += d;
            h[4] += e;
            h[5] += f;
            h[6] += g;
            h[7] += hh;
        }

        std::array<uint8_t, 32> result{};

        for (int i = 0; i < 8; ++i) {
            result[i * 4] =
                static_cast<uint8_t>((h[i] >> 24) & 0xff);
            result[i * 4 + 1] =
                static_cast<uint8_t>((h[i] >> 16) & 0xff);
            result[i * 4 + 2] =
                static_cast<uint8_t>((h[i] >> 8) & 0xff);
            result[i * 4 + 3] =
                static_cast<uint8_t>(h[i] & 0xff);
        }

        return result;
    }
};

class PasswordHasher {
private:
    static constexpr uint32_t ITERATIONS = 120000;
    static constexpr size_t SALT_SIZE = 16;
    static constexpr size_t KEY_SIZE = 32;
    std::random_device randomDevice;

    static std::vector<uint8_t> toBytes(const std::string& text) {
        return std::vector<uint8_t>(text.begin(), text.end());
    }

    static std::vector<uint8_t> concatenate(
        const std::vector<uint8_t>& a,
        const std::vector<uint8_t>& b
    ) {
        std::vector<uint8_t> result;
        result.reserve(a.size() + b.size());
        result.insert(result.end(), a.begin(), a.end());
        result.insert(result.end(), b.begin(), b.end());
        return result;
    }

    static std::vector<uint8_t> hmacSha256(
        const std::vector<uint8_t>& key,
        const std::vector<uint8_t>& message
    ) {
        constexpr size_t blockSize = 64;
        std::vector<uint8_t> normalizedKey = key;

        if (normalizedKey.size() > blockSize) {
            const auto digest = Sha256::hash(normalizedKey);
            normalizedKey.assign(digest.begin(), digest.end());
        }

        normalizedKey.resize(blockSize, 0);

        std::vector<uint8_t> inner(blockSize);
        std::vector<uint8_t> outer(blockSize);

        for (size_t i = 0; i < blockSize; ++i) {
            inner[i] = normalizedKey[i] ^ 0x36;
            outer[i] = normalizedKey[i] ^ 0x5c;
        }

        const auto innerData = concatenate(inner, message);
        const auto innerDigest = Sha256::hash(innerData);

        std::vector<uint8_t> outerData = outer;
        outerData.insert(
            outerData.end(),
            innerDigest.begin(),
            innerDigest.end()
        );

        const auto finalDigest = Sha256::hash(outerData);

        return {
            finalDigest.begin(),
            finalDigest.end()
        };
    }

    static std::vector<uint8_t> pbkdf2(
        const std::string& password,
        const std::vector<uint8_t>& salt,
        uint32_t iterations
    ) {
        std::vector<uint8_t> result;
        const std::vector<uint8_t> key = toBytes(password);

        // PBKDF2 derives blocks independently. Only one block is needed for
        // the 32-byte SHA-256 output used by this example.
        std::vector<uint8_t> saltAndCounter = salt;
        saltAndCounter.push_back(0);
        saltAndCounter.push_back(0);
        saltAndCounter.push_back(0);
        saltAndCounter.push_back(1);

        std::vector<uint8_t> u =
            hmacSha256(key, saltAndCounter);

        std::vector<uint8_t> t = u;

        for (uint32_t i = 1; i < iterations; ++i) {
            u = hmacSha256(key, u);

            for (size_t j = 0; j < t.size(); ++j) {
                t[j] ^= u[j];
            }
        }

        result.insert(result.end(), t.begin(), t.end());
        result.resize(KEY_SIZE);

        return result;
    }

    static bool constantTimeEqual(
        const std::vector<uint8_t>& a,
        const std::vector<uint8_t>& b
    ) {
        if (a.size() != b.size()) {
            return false;
        }

        uint8_t difference = 0;

        for (size_t i = 0; i < a.size(); ++i) {
            difference |= a[i] ^ b[i];
        }

        return difference == 0;
    }

public:
    struct Record {
        std::vector<uint8_t> salt;
        std::vector<uint8_t> digest;
        uint32_t iterations;
    };

    Record hashPassword(const std::string& password) {
        if (password.empty()) {
            throw std::invalid_argument("Password cannot be empty.");
        }

        if (password.size() > 1024) {
            throw std::invalid_argument("Password is too long.");
        }

        std::vector<uint8_t> salt(SALT_SIZE);

        for (auto& byte : salt) {
            byte = static_cast<uint8_t>(randomDevice());
        }

        return {
            salt,
            pbkdf2(password, salt, ITERATIONS),
            ITERATIONS
        };
    }

    bool verifyPassword(
        const std::string& password,
        const Record& record
    ) const {
        if (password.empty() ||
            record.salt.size() < SALT_SIZE ||
            record.digest.size() != KEY_SIZE ||
            record.iterations == 0) {
            return false;
        }

        const auto derived =
            pbkdf2(password, record.salt, record.iterations);

        return constantTimeEqual(derived, record.digest);
    }

    static std::string hex(const std::vector<uint8_t>& bytes) {
        std::ostringstream output;

        for (uint8_t byte : bytes) {
            output << std::hex
                   << std::setw(2)
                   << std::setfill('0')
                   << static_cast<int>(byte);
        }

        return output.str();
    }
};

int main() {
    try {
        PasswordHasher hasher;

        const std::string password =
            "CorrectHorseBatteryStaple!2026";

        const auto record = hasher.hashPassword(password);

        std::cout << "Password-security record\n";
        std::cout << "Iterations: "
                  << record.iterations << '\n';
        std::cout << "Salt: "
                  << PasswordHasher::hex(record.salt) << '\n';
        std::cout << "Derived key: "
                  << PasswordHasher::hex(record.digest) << '\n';

        std::cout << "\nAuthentication checks\n";

        std::cout
            << "Correct password: "
            << std::boolalpha
            << hasher.verifyPassword(password, record)
            << '\n';

        std::cout
            << "Incorrect password: "
            << hasher.verifyPassword(
                "CorrectHorseBatteryStaple!2025",
                record
            )
            << '\n';

        const auto secondRecord = hasher.hashPassword(password);

        std::cout << "\nSalt uniqueness\n";
        std::cout
            << "Different salts: "
            << (record.salt != secondRecord.salt)
            << '\n';

        std::cout
            << "Different derived keys: "
            << (record.digest != secondRecord.digest)
            << '\n';

        std::cout << "\nBrute-force simulation\n";

        const std::vector<std::string> candidates = {
            "password",
            "123456",
            "qwerty",
            "letmein",
            password
        };

        for (const auto& candidate : candidates) {
            std::cout
                << candidate
                << " -> "
                << (hasher.verifyPassword(candidate, record)
                    ? "accepted"
                    : "rejected")
                << '\n';
        }
    }
    catch (const std::exception& error) {
        std::cerr
            << "Password-security failure: "
            << error.what()
            << '\n';

        return 1;
    }

    return 0;
}
