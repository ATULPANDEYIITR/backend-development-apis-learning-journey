/*
 * Substitution Ciphers
 * ====================
 *
 * C++17 case study:
 * Secure Message Routing and Classical Cipher Analysis
 *
 * This program models a small message-processing system that:
 *   1. Accepts messages from simulated users.
 *   2. Validates substitution keys.
 *   3. Encrypts and decrypts messages.
 *   4. Supports Caesar, affine, and general substitution mechanisms.
 *   5. Performs frequency analysis.
 *   6. Attempts Caesar cryptanalysis.
 *   7. Records processing metadata.
 *   8. Demonstrates edge cases and failure handling.
 *
 * Compile:
 *   g++ -std=c++17 -O2 substitution_ciphers.cpp -o substitution_ciphers
 */

#include <algorithm>
#include <array>
#include <chrono>
#include <cctype>
#include <cmath>
#include <exception>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <optional>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using namespace std;

namespace crypto {

constexpr int ALPHABET_SIZE = 26;
const string ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

const array<double, 26> ENGLISH_FREQUENCIES = {
    0.0812, 0.0149, 0.0271, 0.0432, 0.1202, 0.0230, 0.0203,
    0.0592, 0.0731, 0.0010, 0.0069, 0.0398, 0.0261, 0.0695,
    0.0768, 0.0182, 0.0011, 0.0602, 0.0628, 0.0910, 0.0288,
    0.0111, 0.0209, 0.0017, 0.0211, 0.0007
};

struct FrequencyResult {
    array<size_t, 26> counts{};
    size_t total = 0;
};

struct Candidate {
    int key;
    double score;
    string plaintext;
};

int gcd(int a, int b) {
    a = abs(a);
    b = abs(b);

    while (b != 0) {
        int remainder = a % b;
        a = b;
        b = remainder;
    }

    return a;
}

optional<int> modularInverse(int value, int modulus) {
    value %= modulus;

    if (value < 0) {
        value += modulus;
    }

    int oldR = value;
    int r = modulus;
    int oldS = 1;
    int s = 0;

    while (r != 0) {
        int quotient = oldR / r;

        int nextR = oldR - quotient * r;
        oldR = r;
        r = nextR;

        int nextS = oldS - quotient * s;
        oldS = s;
        s = nextS;
    }

    if (oldR != 1) {
        return nullopt;
    }

    int result = oldS % modulus;

    if (result < 0) {
        result += modulus;
    }

    return result;
}

bool isAsciiLetter(char character) {
    return std::isalpha(static_cast<unsigned char>(character)) != 0
           && std::toupper(static_cast<unsigned char>(character)) >= 'A'
           && std::toupper(static_cast<unsigned char>(character)) <= 'Z';
}

int letterToNumber(char character) {
    char upper = static_cast<char>(
        std::toupper(static_cast<unsigned char>(character))
    );

    if (upper < 'A' || upper > 'Z') {
        throw invalid_argument("Expected an English alphabetic character.");
    }

    return upper - 'A';
}

char numberToLetter(int number) {
    if (number < 0 || number >= ALPHABET_SIZE) {
        throw invalid_argument("Letter number must be in [0, 25].");
    }

    return static_cast<char>('A' + number);
}

char preserveCase(char source, char replacement) {
    if (std::islower(static_cast<unsigned char>(source))) {
        return static_cast<char>(
            std::tolower(static_cast<unsigned char>(replacement))
        );
    }

    return replacement;
}

string caesarEncrypt(const string& text, int shift) {
    string result;
    result.reserve(text.size());

    int normalizedShift = ((shift % 26) + 26) % 26;

    for (char character : text) {
        if (!isAsciiLetter(character)) {
            result.push_back(character);
            continue;
        }

        int plaintextNumber = letterToNumber(character);
        int ciphertextNumber =
            (plaintextNumber + normalizedShift) % 26;

        result.push_back(
            preserveCase(
                character,
                numberToLetter(ciphertextNumber)
            )
        );
    }

    return result;
}

string caesarDecrypt(const string& text, int shift) {
    return caesarEncrypt(text, -shift);
}

void validateSubstitutionKey(const string& key) {
    if (key.size() != ALPHABET_SIZE) {
        throw invalid_argument(
            "Substitution key must contain exactly 26 letters."
        );
    }

    array<bool, 26> seen{};

    for (char character : key) {
        char upper = static_cast<char>(
            std::toupper(static_cast<unsigned char>(character))
        );

        if (upper < 'A' || upper > 'Z') {
            throw invalid_argument(
                "Substitution key may contain only A-Z."
            );
        }

        int index = upper - 'A';

        if (seen[index]) {
            throw invalid_argument(
                "Substitution key contains duplicate letters."
            );
        }

        seen[index] = true;
    }
}

class SubstitutionCipher {
private:
    string key_;
    array<char, 26> encryptionMap_{};
    array<char, 26> decryptionMap_{};

public:
    explicit SubstitutionCipher(string key) {
        for (char& character : key) {
            character = static_cast<char>(
                std::toupper(static_cast<unsigned char>(character))
            );
        }

        validateSubstitutionKey(key);

        key_ = std::move(key);

        for (int i = 0; i < 26; ++i) {
            encryptionMap_[i] = key_[i];
            decryptionMap_[key_[i] - 'A'] =
                static_cast<char>('A' + i);
        }
    }

    const string& key() const {
        return key_;
    }

    string encrypt(const string& plaintext) const {
        string result;
        result.reserve(plaintext.size());

        for (char character : plaintext) {
            if (!isAsciiLetter(character)) {
                result.push_back(character);
                continue;
            }

            int index = letterToNumber(character);
            char replacement = encryptionMap_[index];

            result.push_back(
                preserveCase(character, replacement)
            );
        }

        return result;
    }

    string decrypt(const string& ciphertext) const {
        string result;
        result.reserve(ciphertext.size());

        for (char character : ciphertext) {
            if (!isAsciiLetter(character)) {
                result.push_back(character);
                continue;
            }

            int index = letterToNumber(character);
            char replacement = decryptionMap_[index];

            result.push_back(
                preserveCase(character, replacement)
            );
        }

        return result;
    }
};

string atbash(const string& text) {
    string result;
    result.reserve(text.size());

    for (char character : text) {
        if (!isAsciiLetter(character)) {
            result.push_back(character);
            continue;
        }

        int value = letterToNumber(character);
        char replacement = numberToLetter(25 - value);

        result.push_back(
            preserveCase(character, replacement)
        );
    }

    return result;
}

string affineEncrypt(
    const string& text,
    int a,
    int b
) {
    if (gcd(a, 26) != 1) {
        throw invalid_argument(
            "Affine multiplier a must be coprime with 26."
        );
    }

    string result;
    result.reserve(text.size());

    for (char character : text) {
        if (!isAsciiLetter(character)) {
            result.push_back(character);
            continue;
        }

        int p = letterToNumber(character);
        int c = ((a * p + b) % 26 + 26) % 26;

        result.push_back(
            preserveCase(character, numberToLetter(c))
        );
    }

    return result;
}

string affineDecrypt(
    const string& text,
    int a,
    int b
) {
    optional<int> inverseA = modularInverse(a, 26);

    if (!inverseA.has_value()) {
        throw invalid_argument(
            "Affine multiplier has no modular inverse."
        );
    }

    string result;
    result.reserve(text.size());

    for (char character : text) {
        if (!isAsciiLetter(character)) {
            result.push_back(character);
            continue;
        }

        int c = letterToNumber(character);
        int p = (
            (*inverseA * (c - b)) % 26 + 26
        ) % 26;

        result.push_back(
            preserveCase(character, numberToLetter(p))
        );
    }

    return result;
}

string keywordSubstitutionKey(const string& keyword) {
    array<bool, 26> used{};
    string key;

    for (char character : keyword) {
        if (!isAsciiLetter(character)) {
            continue;
        }

        int index = letterToNumber(character);

        if (!used[index]) {
            used[index] = true;
            key.push_back(static_cast<char>('A' + index));
        }
    }

    for (char character : ALPHABET) {
        int index = character - 'A';

        if (!used[index]) {
            key.push_back(character);
        }
    }

    return key;
}

FrequencyResult frequencyAnalysis(const string& text) {
    FrequencyResult result;

    for (char character : text) {
        if (!isAsciiLetter(character)) {
            continue;
        }

        int index = letterToNumber(character);
        ++result.counts[index];
        ++result.total;
    }

    return result;
}

double chiSquaredScore(const string& text) {
    FrequencyResult frequencies = frequencyAnalysis(text);

    if (frequencies.total == 0) {
        return numeric_limits<double>::infinity();
    }

    double score = 0.0;

    for (int i = 0; i < 26; ++i) {
        double expected =
            ENGLISH_FREQUENCIES[i] * frequencies.total;

        double observed =
            static_cast<double>(frequencies.counts[i]);

        if (expected > 0.0) {
            double difference = observed - expected;
            score += (difference * difference) / expected;
        }
    }

    return score;
}

vector<Candidate> breakCaesar(const string& ciphertext) {
    vector<Candidate> candidates;

    for (int key = 0; key < 26; ++key) {
        string plaintext = caesarDecrypt(ciphertext, key);

        candidates.push_back({
            key,
            chiSquaredScore(plaintext),
            plaintext
        });
    }

    sort(
        candidates.begin(),
        candidates.end(),
        [](const Candidate& left, const Candidate& right) {
            return left.score < right.score;
        }
    );

    return candidates;
}

double indexOfCoincidence(const string& text) {
    FrequencyResult frequencies = frequencyAnalysis(text);

    if (frequencies.total < 2) {
        return 0.0;
    }

    double numerator = 0.0;

    for (size_t count : frequencies.counts) {
        numerator +=
            static_cast<double>(count) *
            static_cast<double>(count - 1);
    }

    double denominator =
        static_cast<double>(frequencies.total) *
        static_cast<double>(frequencies.total - 1);

    return numerator / denominator;
}

class MessageRouter {
private:
    struct MessageRecord {
        string sender;
        string plaintext;
        string ciphertext;
        size_t characterCount;
        double processingMilliseconds;
    };

    vector<MessageRecord> records_;

public:
    void processMessage(
        const string& sender,
        const string& plaintext,
        const SubstitutionCipher& cipher
    ) {
        auto start = chrono::high_resolution_clock::now();

        string ciphertext = cipher.encrypt(plaintext);

        auto end = chrono::high_resolution_clock::now();

        double milliseconds =
            chrono::duration<double, milli>(
                end - start
            ).count();

        records_.push_back({
            sender,
            plaintext,
            ciphertext,
            plaintext.size(),
            milliseconds
        });
    }

    void printReport() const {
        cout << "\nMESSAGE ROUTER REPORT\n";
        cout << string(78, '-') << '\n';

        for (const auto& record : records_) {
            cout << "Sender       : " << record.sender << '\n';
            cout << "Characters   : " << record.characterCount << '\n';
            cout << "Plaintext    : " << record.plaintext << '\n';
            cout << "Ciphertext   : " << record.ciphertext << '\n';
            cout << fixed << setprecision(6);
            cout << "Time         : "
                 << record.processingMilliseconds
                 << " ms\n";
            cout << string(78, '-') << '\n';
        }
    }

    size_t size() const {
        return records_.size();
    }
};

void printFrequencyTable(const string& text) {
    FrequencyResult result = frequencyAnalysis(text);

    cout << "\nFrequency table:\n";

    for (int i = 0; i < 26; ++i) {
        if (result.counts[i] == 0) {
            continue;
        }

        double percentage =
            100.0 * result.counts[i] /
            static_cast<double>(result.total);

        cout << static_cast<char>('A' + i)
             << ": "
             << result.counts[i]
             << " ("
             << fixed << setprecision(2)
             << percentage
             << "%)\n";
    }
}

string makeLargeMessage(size_t repetitions) {
    const string sentence =
        "Substitution ciphers replace plaintext symbols using "
        "a deterministic mapping while preserving statistical "
        "properties that can help cryptanalysis. ";

    string result;

    for (size_t i = 0; i < repetitions; ++i) {
        result += sentence;
    }

    return result;
}

void testCaesar() {
    cout << "\n1. CAESAR CIPHER\n";
    cout << string(78, '=') << '\n';

    string plaintext = "Attack at Dawn!";
    int shift = 3;

    string ciphertext = caesarEncrypt(plaintext, shift);
    string recovered = caesarDecrypt(ciphertext, shift);

    cout << "Plaintext : " << plaintext << '\n';
    cout << "Ciphertext: " << ciphertext << '\n';
    cout << "Recovered : " << recovered << '\n';

    if (recovered != plaintext) {
        throw runtime_error("Caesar round-trip test failed.");
    }
}

void testGeneralSubstitution() {
    cout << "\n2. GENERAL SUBSTITUTION\n";
    cout << string(78, '=') << '\n';

    const string key = "QWERTYUIOPASDFGHJKLZXCVBNM";

    SubstitutionCipher cipher(key);

    string plaintext =
        "The quick brown fox jumps over the lazy dog.";

    string ciphertext = cipher.encrypt(plaintext);
    string recovered = cipher.decrypt(ciphertext);

    cout << "Key       : " << key << '\n';
    cout << "Plaintext : " << plaintext << '\n';
    cout << "Ciphertext: " << ciphertext << '\n';
    cout << "Recovered : " << recovered << '\n';

    if (recovered != plaintext) {
        throw runtime_error(
            "General substitution round-trip failed."
        );
    }
}

void testAffine() {
    cout << "\n3. AFFINE CIPHER\n";
    cout << string(78, '=') << '\n';

    const string plaintext =
        "Affine encryption uses modular arithmetic.";

    const int a = 5;
    const int b = 8;

    string ciphertext =
        affineEncrypt(plaintext, a, b);

    string recovered =
        affineDecrypt(ciphertext, a, b);

    cout << "Parameters: a=" << a << ", b=" << b << '\n';
    cout << "Plaintext : " << plaintext << '\n';
    cout << "Ciphertext: " << ciphertext << '\n';
    cout << "Recovered : " << recovered << '\n';

    if (recovered != plaintext) {
        throw runtime_error(
            "Affine round-trip test failed."
        );
    }
}

void testAtbash() {
    cout << "\n4. ATBASH\n";
    cout << string(78, '=') << '\n';

    const string plaintext =
        "Substitution ciphers";

    const string ciphertext = atbash(plaintext);
    const string recovered = atbash(ciphertext);

    cout << "Plaintext : " << plaintext << '\n';
    cout << "Ciphertext: " << ciphertext << '\n';
    cout << "Recovered : " << recovered << '\n';

    if (recovered != plaintext) {
        throw runtime_error("Atbash round-trip failed.");
    }
}

void testKeywordSubstitution() {
    cout << "\n5. KEYWORD SUBSTITUTION\n";
    cout << string(78, '=') << '\n';

    const string keyword = "CRYPTOGRAPHY";
    const string key =
        keywordSubstitutionKey(keyword);

    SubstitutionCipher cipher(key);

    const string plaintext =
        "Protect important messages.";

    const string ciphertext =
        cipher.encrypt(plaintext);

    const string recovered =
        cipher.decrypt(ciphertext);

    cout << "Keyword   : " << keyword << '\n';
    cout << "Key       : " << key << '\n';
    cout << "Plaintext : " << plaintext << '\n';
    cout << "Ciphertext: " << ciphertext << '\n';
    cout << "Recovered : " << recovered << '\n';
}

void testCryptanalysis() {
    cout << "\n6. CAESAR CRYPTANALYSIS\n";
    cout << string(78, '=') << '\n';

    const int hiddenKey = 17;

    const string plaintext =
        "Cryptography protects information by transforming readable "
        "data into a representation that unauthorized readers should "
        "not understand.";

    const string ciphertext =
        caesarEncrypt(plaintext, hiddenKey);

    cout << "Ciphertext:\n" << ciphertext << "\n\n";

    vector<Candidate> candidates =
        breakCaesar(ciphertext);

    cout << "Top candidate keys:\n";

    size_t limit = min<size_t>(5, candidates.size());

    for (size_t i = 0; i < limit; ++i) {
        const auto& candidate = candidates[i];

        cout << "key="
             << setw(2)
             << candidate.key
             << " score="
             << setw(10)
             << fixed
             << setprecision(2)
             << candidate.score
             << " text="
             << candidate.plaintext.substr(0, 90)
             << '\n';
    }

    cout << "\nActual key: " << hiddenKey << '\n';
}

void testFrequencyAnalysis() {
    cout << "\n7. FREQUENCY ANALYSIS\n";
    cout << string(78, '=') << '\n';

    const string text =
        "The quick brown fox jumps over the lazy dog. "
        "The quick brown fox jumps over the lazy dog.";

    printFrequencyTable(text);

    cout << "\nIndex of coincidence: "
         << fixed
         << setprecision(5)
         << indexOfCoincidence(text)
         << '\n';
}

void demonstrateFailureConditions() {
    cout << "\n8. FAILURE CONDITIONS AND VALIDATION\n";
    cout << string(78, '=') << '\n';

    vector<string> invalidKeys = {
        "ABC",
        "AAAAAAAAAAAAAAAAAAAAAAAAAA",
        "ABCDEFGHIJKLMNOPQRSTUVWXY1",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZABC"
    };

    for (const string& invalidKey : invalidKeys) {
        try {
            SubstitutionCipher cipher(invalidKey);
            cout << "Unexpectedly accepted key: "
                 << invalidKey << '\n';
        }
        catch (const exception& error) {
            cout << "Rejected invalid key \""
                 << invalidKey
                 << "\": "
                 << error.what()
                 << '\n';
        }
    }

    try {
        affineEncrypt("HELLO", 13, 5);
        cout << "Unexpectedly accepted invalid affine key.\n";
    }
    catch (const exception& error) {
        cout << "Rejected invalid affine parameters: "
             << error.what()
             << '\n';
    }
}

void demonstrateMessageRouter() {
    cout << "\n9. INDUSTRY-STYLE MESSAGE ROUTER CASE STUDY\n";
    cout << string(78, '=') << '\n';

    /*
     * Architecture:
     *
     * MessageRouter owns message records.
     * SubstitutionCipher owns the validated key and mapping.
     * The routing layer does not need to know how individual letters
     * are mapped. This separation makes the design easier to test.
     */
    const string key =
        keywordSubstitutionKey("SECURITY");

    SubstitutionCipher cipher(key);

    MessageRouter router;

    router.processMessage(
        "Node-A",
        "Transfer the encrypted message after validation.",
        cipher
    );

    router.processMessage(
        "Node-B",
        "The receiver must decrypt the ciphertext using the same key.",
        cipher
    );

    router.processMessage(
        "Node-C",
        "Punctuation, spaces, and letter case are preserved.",
        cipher
    );

    router.printReport();

    cout << "Messages processed: "
         << router.size()
         << '\n';
}

void demonstrateLargeWorkload() {
    cout << "\n10. PERFORMANCE AND SCALABILITY\n";
    cout << string(78, '=') << '\n';

    const string key =
        keywordSubstitutionKey("PERFORMANCE");

    SubstitutionCipher cipher(key);

    const string largeMessage =
        makeLargeMessage(100000);

    auto start = chrono::high_resolution_clock::now();

    const string ciphertext =
        cipher.encrypt(largeMessage);

    const string recovered =
        cipher.decrypt(ciphertext);

    auto end = chrono::high_resolution_clock::now();

    double milliseconds =
        chrono::duration<double, milli>(
            end - start
        ).count();

    cout << "Input characters: "
         << largeMessage.size()
         << '\n';

    cout << "Processing time: "
         << fixed
         << setprecision(3)
         << milliseconds
         << " ms\n";

    cout << "Round trip correct: "
         << boolalpha
         << (recovered == largeMessage)
         << '\n';

    /*
     * For a fixed 26-character alphabet:
     *
     * Encryption: O(n)
     * Decryption: O(n)
     * Frequency analysis: O(n)
     * Caesar brute force: O(26n), effectively O(n) for this alphabet
     *
     * Memory:
     * Output storage is O(n), while the substitution map itself is O(26).
     */
}

void demonstrateKeyProperties() {
    cout << "\n11. KEY STRUCTURE AND MATHEMATICAL PROPERTIES\n";
    cout << string(78, '=') << '\n';

    cout << "Valid affine multipliers modulo 26:\n";

    for (int a = 0; a < 26; ++a) {
        if (gcd(a, 26) == 1) {
            cout << a << ' ';
        }
    }

    cout << "\n\nModular inverse examples:\n";

    for (int value : {1, 3, 5, 7, 9, 11, 15, 17, 19, 21, 23, 25}) {
        auto inverse = modularInverse(value, 26);

        if (inverse.has_value()) {
            cout << value
                 << "^-1 mod 26 = "
                 << *inverse
                 << '\n';
        }
    }
}

void runSelfTests() {
    cout << "\n12. SELF-TESTS\n";
    cout << string(78, '=') << '\n';

    {
        string text = "ABC XYZ";
        string encrypted = caesarEncrypt(text, 3);
        string recovered = caesarDecrypt(encrypted, 3);

        if (encrypted != "DEF ABC" || recovered != text) {
            throw runtime_error("Caesar self-test failed.");
        }
    }

    {
        const string key =
            "QWERTYUIOPASDFGHJKLZXCVBNM";

        SubstitutionCipher cipher(key);

        string text = "Testing substitution!";
        string encrypted = cipher.encrypt(text);
        string recovered = cipher.decrypt(encrypted);

        if (recovered != text) {
            throw runtime_error(
                "Substitution self-test failed."
            );
        }
    }

    {
        string text = "Atbash is self inverse.";
        if (atbash(atbash(text)) != text) {
            throw runtime_error(
                "Atbash self-test failed."
            );
        }
    }

    {
        string text = "Affine test.";
        string encrypted =
            affineEncrypt(text, 5, 8);

        string recovered =
            affineDecrypt(encrypted, 5, 8);

        if (recovered != text) {
            throw runtime_error(
                "Affine self-test failed."
            );
        }
    }

    if (gcd(5, 26) != 1) {
        throw runtime_error("GCD self-test failed.");
    }

    if (!modularInverse(5, 26).has_value()
        || *modularInverse(5, 26) != 21) {
        throw runtime_error(
            "Modular inverse self-test failed."
        );
    }

    cout << "All C++ self-tests passed.\n";
}

} // namespace crypto

int main() {
    using namespace crypto;

    try {
        cout << "SUBSTITUTION CIPHERS: C++ TECHNICAL CASE STUDY\n";
        cout << "Alphabet: " << ALPHABET << "\n";

        testCaesar();
        testGeneralSubstitution();
        testAffine();
        testAtbash();
        testKeywordSubstitution();
        testCryptanalysis();
        testFrequencyAnalysis();
        demonstrateFailureConditions();
        demonstrateMessageRouter();
        demonstrateLargeWorkload();
        demonstrateKeyProperties();
        runSelfTests();

        cout << "\n13. SECURITY DESIGN OBSERVATIONS\n";
        cout << string(78, '=') << '\n';

        cout
            << "Classical substitution provides deterministic symbol mapping "
            << "rather than modern semantic security.\n";

        cout
            << "A monoalphabetic substitution preserves symbol frequencies, "
            << "repeated-letter structure, and many language-level patterns.\n";

        cout
            << "A large permutation key space does not eliminate these "
            << "statistical weaknesses.\n";

        cout
            << "For real confidentiality, authenticated modern cryptographic "
            << "algorithms should replace classical substitution mechanisms.\n";

        cout << "\nProgram completed successfully.\n";
    }
    catch (const exception& error) {
        cerr << "\nFatal error: "
             << error.what()
             << '\n';

        return 1;
    }

    return 0;
}
