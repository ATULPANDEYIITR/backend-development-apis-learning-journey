'use strict';

/*
 * Repository Pattern in JavaScript
 *
 * The application layer talks to a repository interface represented by the
 * expected method contract. Storage-specific behavior remains inside the
 * repository implementation.
 *
 * This example uses an event-driven repository to show a useful JavaScript
 * distinction: persistence operations can naturally return Promises and emit
 * domain-relevant events without exposing storage details to the service.
 */

class RepositoryError extends Error {
    constructor(message, code = 'REPOSITORY_ERROR') {
        super(message);
        this.name = 'RepositoryError';
        this.code = code;
    }
}

class User {
    constructor({ id, name, email, active = true }) {
        this.id = id;
        this.name = name;
        this.email = email;
        this.active = active;
    }
}

class MemoryUserRepository {
    constructor() {
        this.users = new Map();
        this.nextId = 1;
    }

    async findById(id) {
        return this.users.get(id) ?? null;
    }

    async findByEmail(email) {
        const normalized = email.trim().toLowerCase();

        for (const user of this.users.values()) {
            if (user.email === normalized) {
                return user;
            }
        }

        return null;
    }

    async save(user) {
        const existing = await this.findByEmail(user.email);

        if (existing && existing.id !== user.id) {
            throw new RepositoryError(
                'Email address already exists',
                'DUPLICATE_EMAIL'
            );
        }

        if (user.id === null || user.id === undefined) {
            user.id = this.nextId++;
        }

        this.users.set(user.id, user);
        return user;
    }

    async listActive() {
        return [...this.users.values()].filter(user => user.active);
    }

    async delete(id) {
        return this.users.delete(id);
    }
}

/*
 * This repository models a remote data-access boundary. The delay represents
 * asynchronous I/O without requiring a third-party package or a real server.
 * Application code must therefore use async/await rather than assuming that
 * persistence is immediately available.
 */
class RemoteUserRepository {
    constructor(seed = []) {
        this.remoteData = new Map(seed.map(user => [user.id, user]));
        this.nextId = Math.max(0, ...this.remoteData.keys()) + 1;
    }

    async simulateNetwork() {
        await new Promise(resolve => setTimeout(resolve, 10));
    }

    async findById(id) {
        await this.simulateNetwork();
        return this.remoteData.get(id) ?? null;
    }

    async findByEmail(email) {
        await this.simulateNetwork();
        const normalized = email.trim().toLowerCase();

        for (const user of this.remoteData.values()) {
            if (user.email === normalized) {
                return user;
            }
        }

        return null;
    }

    async save(user) {
        await this.simulateNetwork();

        const duplicate = await this.findByEmail(user.email);

        if (duplicate && duplicate.id !== user.id) {
            throw new RepositoryError(
                'Remote repository rejected duplicate email',
                'DUPLICATE_EMAIL'
            );
        }

        if (user.id === null || user.id === undefined) {
            user.id = this.nextId++;
        }

        this.remoteData.set(user.id, user);
        return user;
    }

    async listActive() {
        await this.simulateNetwork();
        return [...this.remoteData.values()].filter(user => user.active);
    }

    async delete(id) {
        await this.simulateNetwork();
        return this.remoteData.delete(id);
    }
}

class UserService {
    constructor(repository) {
        this.repository = repository;
    }

    async register(name, email) {
        const cleanName = String(name).trim();
        const cleanEmail = String(email).trim().toLowerCase();

        if (cleanName.length < 2) {
            throw new Error('Name must contain at least two characters');
        }

        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

        if (!emailPattern.test(cleanEmail)) {
            throw new Error('Invalid email address');
        }

        if (await this.repository.findByEmail(cleanEmail)) {
            throw new Error('A user with this email already exists');
        }

        return this.repository.save(
            new User({
                id: null,
                name: cleanName,
                email: cleanEmail,
                active: true
            })
        );
    }

    async deactivate(id) {
        const user = await this.repository.findById(id);

        if (!user) {
            throw new Error(`User ${id} does not exist`);
        }

        if (!user.active) {
            return user;
        }

        user.active = false;
        return this.repository.save(user);
    }

    async activeUserReport() {
        const users = await this.repository.listActive();

        return users.map(user => ({
            id: user.id,
            name: user.name,
            email: user.email
        }));
    }
}

class AuditEventBus {
    constructor() {
        this.listeners = new Map();
    }

    on(eventName, listener) {
        if (!this.listeners.has(eventName)) {
            this.listeners.set(eventName, []);
        }

        this.listeners.get(eventName).push(listener);
    }

    emit(eventName, payload) {
        for (const listener of this.listeners.get(eventName) ?? []) {
            listener(payload);
        }
    }
}

/*
 * The service remains unaware of the event bus and repository internals.
 * The orchestration layer decides which infrastructure components are wired
 * together, which keeps dependencies explicit.
 */
async function runApplication() {
    const repository = new MemoryUserRepository();
    const service = new UserService(repository);
    const events = new AuditEventBus();

    events.on('user.deactivated', user => {
        console.log(`AUDIT: user ${user.id} was deactivated`);
    });

    const firstUser = await service.register(
        'Aarav Mehta',
        'AARAV@example.com'
    );

    const secondUser = await service.register(
        'Neha Singh',
        'neha@example.com'
    );

    console.log('Created users:', firstUser, secondUser);
    console.log('Active report:', await service.activeUserReport());

    await service.deactivate(firstUser.id);

    /*
     * The event is emitted here at the application boundary. In a production
     * system this could be connected to logging, metrics, auditing, or a
     * durable event mechanism without changing repository responsibilities.
     */
    events.emit('user.deactivated', firstUser);

    console.log('After deactivation:', await service.activeUserReport());

    const remoteRepository = new RemoteUserRepository([
        new User({
            id: 100,
            name: 'Remote User',
            email: 'remote@example.com',
            active: true
        })
    ]);

    const remoteService = new UserService(remoteRepository);

    const remoteUser = await remoteService.register(
        'Remote Customer',
        'customer@example.com'
    );

    console.log('Async repository result:', remoteUser);
}

runApplication().catch(error => {
    console.error(`${error.name}: ${error.message}`);
    process.exitCode = 1;
});
