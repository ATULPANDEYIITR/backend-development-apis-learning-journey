'use strict';

/**
 * HTTPS and TLS security assessment.
 *
 * Node.js standard library only.
 *
 * Features:
 * - Real TLS handshake inspection
 * - Certificate chain and hostname validation
 * - Certificate expiry assessment
 * - TLS version and cipher-suite policies
 * - Asynchronous endpoint monitoring
 * - HTTPS termination architecture evaluation
 * - Event-driven audit reporting
 *
 * Run:
 *   node https_tls.js example.com
 *   node https_tls.js example.com google.com --test
 */

const tls = require('node:tls');
const https = require('node:https');
const fs = require('node:fs/promises');
const path = require('node:path');
const { EventEmitter } = require('node:events');
const { isIP } = require('node:net');


const TLS_VERSIONS = Object.freeze({
    TLS_1_2: 'TLSv1.2',
    TLS_1_3: 'TLSv1.3'
});

const TERMINATION_MODES = Object.freeze({
    EDGE: 'edge',
    REVERSE_PROXY: 'reverse_proxy',
    PASSTHROUGH: 'passthrough'
});


class TLSConfigurationError extends Error {
    constructor(message) {
        super(message);
        this.name = 'TLSConfigurationError';
    }
}


class TLSConfiguration {
    constructor({
        hostname,
        port = 443,
        minVersion = TLS_VERSIONS.TLS_1_2,
        timeout = 5000,
        rejectUnauthorized = true
    }) {
        this.hostname = hostname;
        this.port = port;
        this.minVersion = minVersion;
        this.timeout = timeout;
        this.rejectUnauthorized = rejectUnauthorized;

        this.validate();
        Object.freeze(this);
    }

    validate() {
        if (
            typeof this.hostname !== 'string' ||
            this.hostname.trim() === ''
        ) {
            throw new TLSConfigurationError(
                'A hostname is required'
            );
        }

        if (
            !Number.isInteger(this.port) ||
            this.port < 1 ||
            this.port > 65535
        ) {
            throw new TLSConfigurationError(
                'Invalid TCP port'
            );
        }

        if (
            !Object.values(TLS_VERSIONS).includes(
                this.minVersion
            )
        ) {
            throw new TLSConfigurationError(
                'Only TLS 1.2 and TLS 1.3 minimum versions are accepted'
            );
        }

        if (
            !Number.isFinite(this.timeout) ||
            this.timeout <= 0
        ) {
            throw new TLSConfigurationError(
                'Timeout must be positive'
            );
        }
    }
}


class CertificateAnalyzer {
    static analyze(certificate, warningDays = 30) {
        if (
            !Number.isInteger(warningDays) ||
            warningDays < 0
        ) {
            throw new RangeError(
                'Warning days must be a non-negative integer'
            );
        }

        const expiry = new Date(certificate.valid_to);

        if (Number.isNaN(expiry.getTime())) {
            throw new Error('Invalid certificate expiration date');
        }

        const now = Date.now();

        const daysRemaining = Math.floor(
            (expiry.getTime() - now) / 86400000
        );

        let status = 'valid';

        if (daysRemaining < 0) {
            status = 'expired';
        } else if (daysRemaining <= warningDays) {
            status = 'expiring';
        }

        return Object.freeze({
            subject: certificate.subject,
            issuer: certificate.issuer,
            validFrom: certificate.valid_from,
            validTo: certificate.valid_to,
            fingerprint256: certificate.fingerprint256,
            subjectAlternativeNames:
                certificate.subjectaltname || '',
            daysRemaining,
            status
        });
    }
}


class TLSProbe {
    constructor(configuration) {
        this.configuration = configuration;
    }

    inspect() {
        const config = this.configuration;

        return new Promise((resolve) => {
            let completed = false;
            let socket;

            const finish = (result) => {
                if (completed) return;

                completed = true;

                if (socket && !socket.destroyed) {
                    socket.destroy();
                }

                resolve(Object.freeze({
                    hostname: config.hostname,
                    port: config.port,
                    ...result
                }));
            };

            try {
                socket = tls.connect({
                    host: config.hostname,
                    port: config.port,
                    minVersion: config.minVersion,
                    rejectUnauthorized: config.rejectUnauthorized,
                    servername: isIP(config.hostname)
                        ? undefined
                        : config.hostname,
                        timeout: config.timeout
                });

                socket.setTimeout(config.timeout);

                socket.once('secureConnect', () => {
                    try {
                        const certificate =
                            socket.getPeerCertificate(true);

                        if (!certificate || !certificate.raw) {
                            finish({
                                success: false,
                                error: 'Server did not provide a usable certificate'
                            });
                            return;
                        }

                        const cipher = socket.getCipher();

                        finish({
                            success: true,
                            tlsVersion: socket.getProtocol(),
                            cipherSuite: cipher.standardName ||
                                cipher.name,
                            certificate: CertificateAnalyzer.analyze(
                                certificate
                            ),
                            authorized: socket.authorized
                        });
                    } catch (error) {
                        finish({
                            success: false,
                            error: error.message
                        });
                    }
                });

                socket.once('error', (error) => {
                    finish({
                        success: false,
                        error: error.code
                            ? `${error.code}: ${error.message}`
                            : error.message
                    });
                });

                socket.once('timeout', () => {
                    finish({
                        success: false,
                        error: 'TLS handshake timed out'
                    });
                });

            } catch (error) {
                finish({
                    success: false,
                    error: error.message
                });
            }
        });
    }
}


class TerminationPolicy {
    constructor({
        mode,
        frontendTLS = true,
        backendTLS = true,
        secureCookies = true,
        trustedProxyHeaders = true,
        verifyBackendCertificate = true
    }) {
        this.mode = mode;
        this.frontendTLS = frontendTLS;
        this.backendTLS = backendTLS;
        this.secureCookies = secureCookies;
        this.trustedProxyHeaders = trustedProxyHeaders;
        this.verifyBackendCertificate =
            verifyBackendCertificate;
    }

    evaluate() {
        const violations = [];

        if (!Object.values(TERMINATION_MODES).includes(this.mode)) {
            violations.push('Unknown termination mode');
        }

        if (!this.frontendTLS) {
            violations.push('Public frontend must use HTTPS');
        }

        if (
            this.mode === TERMINATION_MODES.EDGE ||
            this.mode === TERMINATION_MODES.REVERSE_PROXY
        ) {
            if (!this.backendTLS) {
                violations.push(
                    'Unencrypted proxy-to-application traffic'
                );
            }

            if (
                this.backendTLS &&
                !this.verifyBackendCertificate
            ) {
                violations.push(
                    'Backend certificate verification is disabled'
                );
            }

            if (!this.trustedProxyHeaders) {
                violations.push(
                    'Proxy protocol metadata is not securely managed'
                );
            }
        }

        if (!this.secureCookies) {
            violations.push('Secure cookie attribute is disabled');
        }

        return {
            mode: this.mode,
            compliant: violations.length === 0,
            violations
        };
    }
}


class HTTPSMonitor extends EventEmitter {
    constructor() {
        super();
        this.results = new Map();
    }

    async inspectEndpoint(hostname, options = {}) {
        const configuration = new TLSConfiguration({
            hostname,
            ...options
        });

        this.emit('inspectionStarted', {
            hostname,
            port: configuration.port
        });

        const result = await new TLSProbe(
            configuration
        ).inspect();

        this.results.set(
            `${hostname}:${configuration.port}`,
            result
        );

        this.emit(
            result.success ? 'inspectionSucceeded' : 'inspectionFailed',
            result
        );

        return result;
    }

    async inspectMany(hostnames, options = {}) {
        const uniqueHosts = [...new Set(hostnames)];

        // Limit simultaneous connections to protect resources.
        const concurrency = 5;
        const results = [];

        for (
            let index = 0;
            index < uniqueHosts.length;
            index += concurrency
        ) {
            const batch = uniqueHosts.slice(
                index,
                index + concurrency
            );

            const batchResults = await Promise.all(
                batch.map(hostname =>
                    this.inspectEndpoint(hostname, options)
                )
            );

            results.push(...batchResults);
        }

        return results;
    }

    summary() {
        const records = [...this.results.values()];
        const successful = records.filter(
            item => item.success
        );

        return {
            total: records.length,
            successful: successful.length,
            failed: records.length - successful.length,
            negotiatedVersions: [
                ...new Set(
                    successful.map(item => item.tlsVersion)
                )
            ],
            certificatesExpiring: successful.filter(
                item => item.certificate?.status === 'expiring'
            ).length,
            expiredCertificates: successful.filter(
                item => item.certificate?.status === 'expired'
            ).length
        };
    }

    async exportReport(filename) {
        const report = {
            generatedAt: new Date().toISOString(),
            summary: this.summary(),
            results: [...this.results.values()]
        };

        const destination = path.resolve(filename);
        const temporary = `${destination}.tmp`;

        await fs.mkdir(path.dirname(destination), {
            recursive: true
        });

        try {
            await fs.writeFile(
                temporary,
                JSON.stringify(report, null, 2),
                {
                    encoding: 'utf8',
                    mode: 0o600,
                    flag: 'w'
                }
            );

            await fs.rename(temporary, destination);
        } catch (error) {
            await fs.rm(temporary, {
                force: true
            });

            throw error;
        }
    }
}


function validateHTTPSRequest(urlString) {
    let parsed;

    try {
        parsed = new URL(urlString);
    } catch {
        throw new TLSConfigurationError(
            'Invalid URL'
        );
    }

    if (parsed.protocol !== 'https:') {
        throw new TLSConfigurationError(
            'Only HTTPS URLs are accepted'
        );
    }

    if (parsed.username || parsed.password) {
        throw new TLSConfigurationError(
            'Credentials must not be embedded in URLs'
        );
    }

    return parsed;
}


function requestHTTPS(urlString, timeout = 5000) {
    const url = validateHTTPSRequest(urlString);

    return new Promise((resolve, reject) => {
        const request = https.request(
            url,
            {
                method: 'GET',
                timeout,
                rejectUnauthorized: true,
                headers: {
                    'Accept': 'application/json, text/html'
                }
            },
            response => {
                const chunks = [];
                let size = 0;
                const maximumSize = 1024 * 1024;

                response.on('data', chunk => {
                    size += chunk.length;

                    if (size > maximumSize) {
                        request.destroy(
                            new Error('Response size limit exceeded')
                        );
                        return;
                    }

                    chunks.push(chunk);
                });

                response.on('end', () => {
                    resolve({
                        statusCode: response.statusCode,
                        headers: response.headers,
                        body: Buffer.concat(chunks).toString('utf8')
                    });
                });
            }
        );

        request.once('timeout', () => {
            request.destroy(
                new Error('HTTPS request timed out')
            );
        });

        request.once('error', reject);
        request.end();
    });
}


function runTests() {
    const assert = require('node:assert/strict');

    assert.throws(
        () => new TLSConfiguration({
            hostname: '',
        }),
        TLSConfigurationError
    );

    assert.throws(
        () => new TLSConfiguration({
            hostname: 'example.com',
            port: 70000
        }),
        TLSConfigurationError
    );

    assert.throws(
        () => validateHTTPSRequest(
            'http://example.com'
        ),
        TLSConfigurationError
    );

    assert.throws(
        () => validateHTTPSRequest(
            'https://user:password@example.com'
        ),
        TLSConfigurationError
    );

    const insecurePolicy = new TerminationPolicy({
        mode: TERMINATION_MODES.REVERSE_PROXY,
        backendTLS: false
    });

    assert.equal(
        insecurePolicy.evaluate().compliant,
        false
    );

    const securePolicy = new TerminationPolicy({
        mode: TERMINATION_MODES.EDGE
    });

    assert.equal(
        securePolicy.evaluate().compliant,
        true
    );

    const invalidMode = new TerminationPolicy({
        mode: 'unknown'
    });

    assert.equal(
        invalidMode.evaluate().compliant,
        false
    );

    console.log('All JavaScript tests passed.');
}


async function main() {
    const argumentsList = process.argv.slice(2);

    if (argumentsList.includes('--test')) {
        runTests();
        return;
    }

    const hosts = argumentsList.filter(
        argument => !argument.startsWith('--')
    );

    if (hosts.length === 0) {
        console.log(
            'Usage: node https_tls.js example.com google.com'
        );
        console.log(
            '       node https_tls.js --test'
        );
        process.exitCode = 1;
        return;
    }

    const monitor = new HTTPSMonitor();

    monitor.on('inspectionStarted', event => {
        console.log(
            `Inspecting ${event.hostname}:${event.port}`
        );
    });

    monitor.on('inspectionFailed', result => {
        console.error(
            `TLS failure: ${result.hostname}: ${result.error}`
        );
    });

    const results = await monitor.inspectMany(hosts);

    for (const result of results) {
        console.log(JSON.stringify(result, null, 2));
    }

    console.log('\nAUDIT SUMMARY');
    console.log(JSON.stringify(
        monitor.summary(),
        null,
        2
    ));

    await monitor.exportReport(
        'reports/tls-audit.json'
    );

    console.log(
        '\nReport saved to reports/tls-audit.json'
    );
}


main().catch(error => {
    console.error('Application error:', error.message);
    process.exitCode = 1;
});
