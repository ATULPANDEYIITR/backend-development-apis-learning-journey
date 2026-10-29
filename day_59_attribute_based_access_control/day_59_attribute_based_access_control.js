"use strict";

const EventEmitter = require("node:events");

const Effect = Object.freeze({
  ALLOW: "allow",
  DENY: "deny"
});

const Decision = Object.freeze({
  ALLOW: "allow",
  DENY: "deny"
});

class AuthorizationError extends Error {}
class InvalidRequestError extends AuthorizationError {}

class Policy {
  constructor({
    id,
    name,
    effect,
    priority,
    actions,
    resourceTypes,
    conditions,
    enabled = true
  }) {
    this.id = id;
    this.name = name;
    this.effect = effect;
    this.priority = priority;
    this.actions = new Set(actions);
    this.resourceTypes = new Set(resourceTypes);
    this.conditions = conditions;
    this.enabled = enabled;
  }

  matches(context) {
    if (!this.enabled) return false;

    const actionMatches =
      this.actions.has("*") || this.actions.has(context.action);

    const resourceMatches =
      this.resourceTypes.has("*") ||
      this.resourceTypes.has(context.resource.type);

    return actionMatches &&
      resourceMatches &&
      this.conditions.every((condition) => condition(context));
  }
}

function getAttribute(context, path) {
  const parts = path.split(".");
  let current = context;

  for (const part of parts) {
    if (current === undefined || current === null) {
      throw new InvalidRequestError(`Missing attribute: ${path}`);
    }
    current = current[part];
  }

  if (current === undefined || current === null) {
    throw new InvalidRequestError(`Missing attribute: ${path}`);
  }

  return current;
}

function equals(attribute, expected) {
  return (context) => getAttribute(context, attribute) === expected;
}

function includes(attribute, expected) {
  return (context) => {
    const value = getAttribute(context, attribute);
    return value instanceof Set
      ? value.has(expected)
      : Array.isArray(value) && value.includes(expected);
  };
}

function lessThanOrEqual(attribute, expected) {
  return (context) => getAttribute(context, attribute) <= expected;
}

function greaterThanOrEqual(attribute, expected) {
  return (context) => getAttribute(context, attribute) >= expected;
}

function matchesRegex(attribute, expression) {
  const regex = new RegExp(expression);
  return (context) => regex.test(String(getAttribute(context, attribute)));
}

function ipInCidr(ip, cidr) {
  const [network, prefixText] = cidr.split("/");
  const prefix = Number(prefixText);

  const ipToNumber = (address) =>
    address
      .split(".")
      .reduce((result, octet) => result * 256 + Number(octet), 0);

  const ipValue = ipToNumber(ip);
  const networkValue = ipToNumber(network);

  if (!Number.isInteger(prefix) || prefix < 0 || prefix > 32) {
    return false;
  }

  const mask = prefix === 0 ? 0 : (0xffffffff << (32 - prefix)) >>> 0;
  return (ipValue >>> 0 & mask) === (networkValue >>> 0 & mask);
}

function ipInRange(attribute, cidr) {
  return (context) => ipInCidr(
    getAttribute(context, attribute),
    cidr
  );
}

class AuthorizationEngine extends EventEmitter {
  constructor(policies) {
    super();
    this.policies = [...policies];
    this.auditLog = [];
  }

  async authorize(context) {
    this.validate(context);

    const matched = this.policies
      .filter((policy) => policy.matches(context))
      .sort((a, b) => b.priority - a.priority);

    let decision = Decision.DENY;
    let reason = "Default deny: no applicable allow policy";

    if (!context.user.active) {
      reason = "Inactive user";
    } else {
      const denyPolicy = matched.find(
        (policy) => policy.effect === Effect.DENY
      );

      const allowPolicy = matched.find(
        (policy) => policy.effect === Effect.ALLOW
      );

      if (denyPolicy) {
        reason = `Explicit deny policy: ${denyPolicy.id}`;
      } else if (allowPolicy) {
        decision = Decision.ALLOW;
        reason = `Allowed by policy: ${allowPolicy.id}`;
      }
    }

    const event = {
      timestamp: new Date().toISOString(),
      userId: context.user.id,
      resourceId: context.resource.id,
      action: context.action,
      decision,
      matchedPolicies: matched.map((policy) => policy.id),
      reason
    };

    this.auditLog.push(event);
    this.emit("authorizationDecision", event);

    return event;
  }

  validate(context) {
    if (!context.user?.id) {
      throw new InvalidRequestError("Missing user id");
    }

    if (!context.resource?.id) {
      throw new InvalidRequestError("Missing resource id");
    }

    if (!context.action) {
      throw new InvalidRequestError("Missing action");
    }

    if (!context.user.roles || !(context.user.roles instanceof Set)) {
      throw new InvalidRequestError("User roles must be a Set");
    }

    if (!context.user.active) {
      return;
    }

    const parts = String(context.request.ip).split(".");
    if (
      parts.length !== 4 ||
      parts.some(
        (part) =>
          !/^\d+$/.test(part) ||
          Number(part) < 0 ||
          Number(part) > 255
      )
    ) {
      throw new InvalidRequestError("Invalid IPv4 address");
    }
  }
}

function createPolicies() {
  return [
    new Policy({
      id: "P001",
      name: "Trusted analyst report access",
      effect: Effect.ALLOW,
      priority: 50,
      actions: ["read"],
      resourceTypes: ["report"],
      conditions: [
        includes("user.roles", "analyst"),
        lessThanOrEqual("resource.classification", 2),
        equals("request.deviceTrusted", true)
      ]
    }),

    new Policy({
      id: "P002",
      name: "Manager confidential access",
      effect: Effect.ALLOW,
      priority: 70,
      actions: ["read"],
      resourceTypes: ["report"],
      conditions: [
        includes("user.roles", "manager"),
        lessThanOrEqual("resource.classification", 4),
        equals("request.mfaVerified", true),
        equals("request.deviceTrusted", true)
      ]
    }),

    new Policy({
      id: "P003",
      name: "Restricted-resource untrusted-device block",
      effect: Effect.DENY,
      priority: 100,
      actions: ["read", "write", "delete"],
      resourceTypes: ["report", "database"],
      conditions: [
        greaterThanOrEqual("resource.classification", 4),
        equals("request.deviceTrusted", false),
        ipInRange("request.ip", "10.0.0.0/8")
      ]
    }),

    new Policy({
      id: "P004",
      name: "Security administrator database access",
      effect: Effect.ALLOW,
      priority: 90,
      actions: ["read", "write", "delete"],
      resourceTypes: ["database"],
      conditions: [
        equals("user.department", "security"),
        includes("user.roles", "administrator"),
        equals("request.mfaVerified", true),
        equals("request.environment", "production")
      ]
    }),

    new Policy({
      id: "P005",
      name: "Incident response access",
      effect: Effect.ALLOW,
      priority: 80,
      actions: ["read"],
      resourceTypes: ["report"],
      conditions: [
        includes("user.roles", "incident_responder"),
        equals("request.mfaVerified", true),
        matchesRegex(
          "request.emergencyTicket",
          "^INC-[0-9]{6}$"
        )
      ]
    })
  ];
}

function user(id, department, roles, clearance, active = true) {
  return {
    id,
    department,
    roles: new Set(roles),
    clearance,
    active
  };
}

function resource(id, type, ownerDepartment, classification) {
  return {
    id,
    type,
    ownerDepartment,
    classification
  };
}

function requestContext(
  currentUser,
  currentResource,
  action,
  overrides = {}
) {
  return {
    user: currentUser,
    resource: currentResource,
    action,
    request: {
      ip: "10.20.30.40",
      deviceTrusted: true,
      mfaVerified: true,
      country: "IN",
      environment: "production",
      emergencyTicket: null,
      ...overrides
    }
  };
}

async function main() {
  const engine = new AuthorizationEngine(createPolicies());

  engine.on("authorizationDecision", (event) => {
    console.log(
      `[audit] ${event.userId} ${event.action} ` +
      `${event.resourceId}: ${event.decision} - ${event.reason}`
    );
  });

  const analyst = user(
    "U100",
    "analytics",
    ["employee", "analyst"],
    2
  );

  const manager = user(
    "U200",
    "operations",
    ["employee", "manager"],
    4
  );

  const administrator = user(
    "U300",
    "security",
    ["employee", "administrator"],
    5
  );

  const responder = user(
    "U400",
    "security",
    ["employee", "incident_responder"],
    5
  );

  const report = resource(
    "R100",
    "report",
    "analytics",
    2
  );

  const confidentialReport = resource(
    "R200",
    "report",
    "security",
    4
  );

  const database = resource(
    "DB100",
    "database",
    "security",
    5
  );

  const requests = [
    [
      "Analyst",
      requestContext(analyst, report, "read", {
        mfaVerified: false
      })
    ],
    [
      "Manager",
      requestContext(manager, confidentialReport, "read")
    ],
    [
      "Manager without MFA",
      requestContext(manager, confidentialReport, "read", {
        mfaVerified: false
      })
    ],
    [
      "Security administrator",
      requestContext(administrator, database, "delete")
    ],
    [
      "Blocked untrusted device",
      requestContext(administrator, database, "read", {
        deviceTrusted: false
      })
    ],
    [
      "Emergency responder",
      requestContext(responder, confidentialReport, "read", {
        emergencyTicket: "INC-123456"
      })
    ]
  ];

  for (const [name, context] of requests) {
    try {
      const result = await engine.authorize(context);
      console.log(`${name}: ${result.decision}`);
    } catch (error) {
      console.error(`${name}: ${error.message}`);
    }
  }

  console.log("\nAudit records:", engine.auditLog.length);

  if (engine.auditLog.length !== requests.length) {
    throw new Error("Unexpected audit-log size");
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
