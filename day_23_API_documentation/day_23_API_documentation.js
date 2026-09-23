/*
 * API Documentation with OpenAPI
 *
 * This standalone JavaScript study file demonstrates:
 * - OpenAPI document structure
 * - API metadata
 * - paths and HTTP operations
 * - operationId
 * - parameters
 * - request bodies
 * - reusable schemas
 * - $ref
 * - responses and status codes
 * - security schemes
 * - Swagger UI integration
 * - ReDoc integration
 * - schema validation
 * - documentation auditing
 * - contract-style testing
 * - asynchronous documentation loading
 *
 * Run with:
 *
 *     node api-documentation.js
 *
 * No external npm package is required.
 */

"use strict";

// -----------------------------------------------------------------------------
// 1. Basic terminology
// -----------------------------------------------------------------------------

function printSection(title) {
  console.log("\n" + "=".repeat(88));
  console.log(title);
  console.log("=".repeat(88));
}

function printSubsection(title) {
  console.log("\n" + "-".repeat(72));
  console.log(title);
  console.log("-".repeat(72));
}

function prettyJson(value) {
  return JSON.stringify(value, null, 2);
}

function explainTerminology() {
  printSection("1. API documentation fundamentals");

  const terms = {
    API: "A defined interface through which software components communicate.",
    OpenAPI:
      "A machine-readable specification format for describing HTTP APIs.",
    "Swagger UI":
      "An interactive documentation renderer that can display an OpenAPI document.",
    ReDoc:
      "A documentation renderer designed around structured API reference presentation.",
    schema:
      "A description of the structure, types, constraints, and relationships of API data.",
    operationId:
      "A unique identifier for one HTTP operation, useful to documentation and code-generation tools.",
    metadata:
      "Descriptive information such as API title, version, description, contact, and license.",
  };

  for (const [name, description] of Object.entries(terms)) {
    console.log(`${name.padEnd(16)} ${description}`);
  }
}

// -----------------------------------------------------------------------------
// 2. Schema examples
// -----------------------------------------------------------------------------

function demonstrateSchemaTypes() {
  printSection("2. Common schema structures");

  const schemas = {
    StringValue: {
      type: "string",
      minLength: 1,
      maxLength: 100,
    },

    IntegerValue: {
      type: "integer",
      format: "int64",
      minimum: 1,
      maximum: 1000000,
    },

    BooleanValue: {
      type: "boolean",
    },

    StatusValue: {
      type: "string",
      enum: ["active", "inactive", "suspended"],
    },

    StringArray: {
      type: "array",
      minItems: 1,
      items: {
        type: "string",
      },
    },

    UserObject: {
      type: "object",
      required: ["id", "name"],
      properties: {
        id: {
          type: "integer",
          format: "int64",
        },
        name: {
          type: "string",
        },
      },
    },
  };

  for (const [name, schema] of Object.entries(schemas)) {
    printSubsection(name);
    console.log(prettyJson(schema));
  }
}

// -----------------------------------------------------------------------------
// 3. Components
// -----------------------------------------------------------------------------

function schemaRef(name) {
  return `#/components/schemas/${name}`;
}

function buildComponents() {
  return {
    schemas: {
      User: {
        type: "object",
        description: "A registered API user.",
        required: ["id", "name", "email", "status"],
        properties: {
          id: {
            type: "integer",
            format: "int64",
            minimum: 1,
            example: 101,
          },
          name: {
            type: "string",
            minLength: 1,
            maxLength: 100,
            example: "Atul Pandey",
          },
          email: {
            type: "string",
            format: "email",
            example: "atul@example.com",
          },
          status: {
            type: "string",
            enum: ["active", "inactive", "suspended"],
            example: "active",
          },
          roles: {
            type: "array",
            minItems: 1,
            items: {
              type: "string",
              enum: ["reader", "editor", "admin"],
            },
          },
        },
      },

      UserCreate: {
        type: "object",
        required: ["name", "email"],
        properties: {
          name: {
            type: "string",
            minLength: 1,
            maxLength: 100,
          },
          email: {
            type: "string",
            format: "email",
          },
          roles: {
            type: "array",
            items: {
              type: "string",
              enum: ["reader", "editor", "admin"],
            },
            default: ["reader"],
          },
        },
      },

      Error: {
        type: "object",
        required: ["code", "message"],
        properties: {
          code: {
            type: "string",
          },
          message: {
            type: "string",
          },
          details: {
            type: "object",
            additionalProperties: true,
          },
        },
      },

      HealthStatus: {
        type: "object",
        required: ["status", "service"],
        properties: {
          status: {
            type: "string",
            enum: ["ok", "degraded"],
          },
          service: {
            type: "string",
          },
          version: {
            type: "string",
          },
        },
      },
    },

    parameters: {
      UserId: {
        name: "user_id",
        in: "path",
        required: true,
        description: "Unique identifier of the user.",
        schema: {
          type: "integer",
          format: "int64",
          minimum: 1,
        },
        example: 101,
      },

      Page: {
        name: "page",
        in: "query",
        required: false,
        schema: {
          type: "integer",
          minimum: 1,
          default: 1,
        },
      },

      PageSize: {
        name: "page_size",
        in: "query",
        required: false,
        schema: {
          type: "integer",
          minimum: 1,
          maximum: 100,
          default: 20,
        },
      },
    },

    responses: {
      BadRequest: {
        description: "The request is invalid.",
        content: {
          "application/json": {
            schema: {
              $ref: schemaRef("Error"),
            },
          },
        },
      },

      NotFound: {
        description: "The requested resource was not found.",
        content: {
          "application/json": {
            schema: {
              $ref: schemaRef("Error"),
            },
          },
        },
      },

      ServerError: {
        description: "An unexpected server error occurred.",
        content: {
          "application/json": {
            schema: {
              $ref: schemaRef("Error"),
            },
          },
        },
      },
    },

    securitySchemes: {
      bearerAuth: {
        type: "http",
        scheme: "bearer",
        bearerFormat: "JWT",
      },
    },
  };
}

// -----------------------------------------------------------------------------
// 4. Operation helpers
// -----------------------------------------------------------------------------

function jsonContent(schema, example) {
  const mediaType = {
    schema,
  };

  if (example !== undefined) {
    mediaType.example = example;
  }

  return {
    "application/json": mediaType,
  };
}

function buildUserOperations() {
  return {
    get: {
      tags: ["Users"],
      summary: "Get a user",
      description: "Returns one user identified by the user_id path parameter.",
      operationId: "getUser",
      parameters: [
        {
          $ref: "#/components/parameters/UserId",
        },
      ],
      responses: {
        "200": {
          description: "User returned successfully.",
          content: jsonContent(
            {
              $ref: schemaRef("User"),
            },
            {
              id: 101,
              name: "Atul Pandey",
              email: "atul@example.com",
              status: "active",
              roles: ["reader"],
            }
          ),
        },

        "400": {
          $ref: "#/components/responses/BadRequest",
        },

        "404": {
          $ref: "#/components/responses/NotFound",
        },

        "500": {
          $ref: "#/components/responses/ServerError",
        },
      },

      security: [
        {
          bearerAuth: [],
        },
      ],
    },

    delete: {
      tags: ["Users"],
      summary: "Delete a user",
      description: "Deletes a user and returns no response body.",
      operationId: "deleteUser",
      parameters: [
        {
          $ref: "#/components/parameters/UserId",
        },
      ],
      responses: {
        "204": {
          description: "User deleted successfully.",
        },

        "400": {
          $ref: "#/components/responses/BadRequest",
        },

        "404": {
          $ref: "#/components/responses/NotFound",
        },
      },

      security: [
        {
          bearerAuth: [],
        },
      ],
    },
  };
}

function buildUserCollectionOperations() {
  return {
    get: {
      tags: ["Users"],
      summary: "List users",
      description:
        "Returns a paginated collection of users. Pagination prevents very large responses.",
      operationId: "listUsers",
      parameters: [
        {
          $ref: "#/components/parameters/Page",
        },
        {
          $ref: "#/components/parameters/PageSize",
        },
      ],
      responses: {
        "200": {
          description: "Users returned successfully.",
          content: {
            "application/json": {
              schema: {
                type: "object",
                required: ["items", "page", "page_size"],
                properties: {
                  items: {
                    type: "array",
                    items: {
                      $ref: schemaRef("User"),
                    },
                  },
                  page: {
                    type: "integer",
                    minimum: 1,
                  },
                  page_size: {
                    type: "integer",
                    minimum: 1,
                    maximum: 100,
                  },
                },
              },
            },
          },
        },

        "400": {
          $ref: "#/components/responses/BadRequest",
        },
      },

      security: [
        {
          bearerAuth: [],
        },
      ],
    },

    post: {
      tags: ["Users"],
      summary: "Create a user",
      description: "Creates a user and returns the new resource.",
      operationId: "createUser",
      requestBody: {
        required: true,
        description: "Information required to create a user.",
        content: {
          "application/json": {
            schema: {
              $ref: schemaRef("UserCreate"),
            },
            example: {
              name: "New User",
              email: "new@example.com",
              roles: ["reader"],
            },
          },
        },
      },

      responses: {
        "201": {
          description: "User created successfully.",
          content: jsonContent({
            $ref: schemaRef("User"),
          }),
        },

        "400": {
          $ref: "#/components/responses/BadRequest",
        },
      },

      security: [
        {
          bearerAuth: [],
        },
      ],
    },
  };
}

// -----------------------------------------------------------------------------
// 5. Complete OpenAPI document
// -----------------------------------------------------------------------------

function buildOpenApiDocument() {
  return {
    openapi: "3.0.3",

    info: {
      title: "User Management API",
      version: "1.0.0",
      description:
        "A documented example API demonstrating OpenAPI metadata, schemas, operations, reusable components, and security.",
      contact: {
        name: "API Engineering Team",
        email: "api@example.com",
      },
      license: {
        name: "Apache 2.0",
      },
    },

    servers: [
      {
        url: "https://api.example.com/v1",
        description: "Production",
      },
      {
        url: "https://staging-api.example.com/v1",
        description: "Staging",
      },
      {
        url: "http://localhost:8000/v1",
        description: "Local development",
      },
    ],

    tags: [
      {
        name: "Users",
        description: "Operations for managing users.",
      },
      {
        name: "Health",
        description: "Service health information.",
      },
    ],

    paths: {
      "/users": buildUserCollectionOperations(),

      "/users/{user_id}": buildUserOperations(),

      "/health": {
        get: {
          tags: ["Health"],
          summary: "Check service health",
          description: "Returns a lightweight service health document.",
          operationId: "getHealth",
          responses: {
            "200": {
              description: "Service health returned.",
              content: jsonContent(
                {
                  $ref: schemaRef("HealthStatus"),
                },
                {
                  status: "ok",
                  service: "user-api",
                  version: "1.0.0",
                }
              ),
            },
          },
        },
      },
    },

    components: buildComponents(),

    security: [
      {
        bearerAuth: [],
      },
    ],
  };
}

// -----------------------------------------------------------------------------
// 6. Operation traversal
// -----------------------------------------------------------------------------

const HTTP_METHODS = new Set([
  "get",
  "post",
  "put",
  "patch",
  "delete",
  "head",
  "options",
  "trace",
]);

function* iterateOperations(document) {
  for (const [path, pathItem] of Object.entries(document.paths || {})) {
    for (const [method, operation] of Object.entries(pathItem)) {
      if (HTTP_METHODS.has(method.toLowerCase())) {
        yield {
          path,
          method: method.toLowerCase(),
          operation,
        };
      }
    }
  }
}

function inspectOperations(document) {
  printSection("3. API operation inventory");

  for (const { path, method, operation } of iterateOperations(document)) {
    console.log(
      `${method.toUpperCase().padEnd(7)} ${path.padEnd(22)} operationId=${operation.operationId}`
    );
  }
}

// -----------------------------------------------------------------------------
// 7. Local $ref resolution
// -----------------------------------------------------------------------------

function decodeJsonPointerToken(token) {
  return token.replace(/~1/g, "/").replace(/~0/g, "~");
}

function resolveLocalRef(document, reference) {
  if (!reference.startsWith("#/")) {
    throw new Error("This example resolves only local references.");
  }

  let current = document;

  const tokens = reference
    .slice(2)
    .split("/")
    .map(decodeJsonPointerToken);

  for (const token of tokens) {
    if (
      current === null ||
      typeof current !== "object" ||
      !Object.prototype.hasOwnProperty.call(current, token)
    ) {
      throw new Error(`Cannot resolve reference token: ${token}`);
    }

    current = current[token];
  }

  return current;
}

function demonstrateRefs(document) {
  printSection("4. Reusable components and $ref");

  const reference =
    document.paths["/users/{user_id}"].get.responses["200"].content[
      "application/json"
    ].schema.$ref;

  console.log("Reference:");
  console.log(reference);

  console.log("\nResolved schema:");
  console.log(prettyJson(resolveLocalRef(document, reference)));
}

// -----------------------------------------------------------------------------
// 8. Schema validation
// -----------------------------------------------------------------------------

class SchemaValidationError extends Error {
  constructor(message) {
    super(message);
    this.name = "SchemaValidationError";
  }
}

function isPlainObject(value) {
  return (
    value !== null &&
    typeof value === "object" &&
    !Array.isArray(value)
  );
}

function validateSchema(value, schema, path = "$") {
  if (value === null) {
    if (schema.nullable === true) {
      return;
    }

    throw new SchemaValidationError(`${path}: null is not permitted`);
  }

  if (Array.isArray(schema.oneOf)) {
    let successCount = 0;

    for (const candidate of schema.oneOf) {
      try {
        validateSchema(value, candidate, path);
        successCount += 1;
      } catch {
        // A failed branch is expected while testing oneOf alternatives.
      }
    }

    if (successCount !== 1) {
      throw new SchemaValidationError(
        `${path}: value must match exactly one oneOf schema`
      );
    }

    return;
  }

  switch (schema.type) {
    case "string":
      if (typeof value !== "string") {
        throw new SchemaValidationError(`${path}: expected string`);
      }

      if (
        schema.minLength !== undefined &&
        value.length < schema.minLength
      ) {
        throw new SchemaValidationError(
          `${path}: shorter than minLength`
        );
      }

      if (
        schema.maxLength !== undefined &&
        value.length > schema.maxLength
      ) {
        throw new SchemaValidationError(
          `${path}: longer than maxLength`
        );
      }

      if (
        schema.pattern !== undefined &&
        !new RegExp(schema.pattern).test(value)
      ) {
        throw new SchemaValidationError(
          `${path}: does not match pattern`
        );
      }
      break;

    case "integer":
      if (!Number.isInteger(value)) {
        throw new SchemaValidationError(`${path}: expected integer`);
      }

      if (
        schema.minimum !== undefined &&
        value < schema.minimum
      ) {
        throw new SchemaValidationError(`${path}: below minimum`);
      }

      if (
        schema.maximum !== undefined &&
        value > schema.maximum
      ) {
        throw new SchemaValidationError(`${path}: above maximum`);
      }
      break;

    case "number":
      if (
        typeof value !== "number" ||
        Number.isNaN(value) ||
        !Number.isFinite(value)
      ) {
        throw new SchemaValidationError(`${path}: expected finite number`);
      }

      if (
        schema.minimum !== undefined &&
        value < schema.minimum
      ) {
        throw new SchemaValidationError(`${path}: below minimum`);
      }

      if (
        schema.maximum !== undefined &&
        value > schema.maximum
      ) {
        throw new SchemaValidationError(`${path}: above maximum`);
      }
      break;

    case "boolean":
      if (typeof value !== "boolean") {
        throw new SchemaValidationError(`${path}: expected boolean`);
      }
      break;

    case "array":
      if (!Array.isArray(value)) {
        throw new SchemaValidationError(`${path}: expected array`);
      }

      if (
        schema.minItems !== undefined &&
        value.length < schema.minItems
      ) {
        throw new SchemaValidationError(`${path}: too few items`);
      }

      if (
        schema.maxItems !== undefined &&
        value.length > schema.maxItems
      ) {
        throw new SchemaValidationError(`${path}: too many items`);
      }

      if (schema.items) {
        value.forEach((item, index) => {
          validateSchema(item, schema.items, `${path}[${index}]`);
        });
      }
      break;

    case "object":
      if (!isPlainObject(value)) {
        throw new SchemaValidationError(`${path}: expected object`);
      }

      for (const requiredProperty of schema.required || []) {
        if (!Object.prototype.hasOwnProperty.call(value, requiredProperty)) {
          throw new SchemaValidationError(
            `${path}: missing required property '${requiredProperty}'`
          );
        }
      }

      for (const [propertyName, propertySchema] of Object.entries(
        schema.properties || {}
      )) {
        if (
          Object.prototype.hasOwnProperty.call(value, propertyName)
        ) {
          validateSchema(
            value[propertyName],
            propertySchema,
            `${path}.${propertyName}`
          );
        }
      }
      break;

    default:
      if (schema.type !== undefined) {
        throw new SchemaValidationError(
          `${path}: unsupported example type ${schema.type}`
        );
      }
  }

  if (
    Array.isArray(schema.enum) &&
    !schema.enum.some((candidate) =>
      Object.is(candidate, value)
    )
  ) {
    throw new SchemaValidationError(
      `${path}: value is not one of the documented enum values`
    );
  }
}

function demonstrateValidation(document) {
  printSection("5. Schema validation");

  const userSchema = resolveLocalRef(
    document,
    "#/components/schemas/User"
  );

  const validUser = {
    id: 101,
    name: "Atul Pandey",
    email: "atul@example.com",
    status: "active",
    roles: ["reader"],
  };

  const invalidUsers = [
    {
      id: 0,
      name: "Atul Pandey",
      email: "atul@example.com",
      status: "active",
      roles: ["reader"],
    },

    {
      id: 101,
      name: "",
      email: "atul@example.com",
      status: "active",
      roles: ["reader"],
    },

    {
      id: 101,
      name: "Atul Pandey",
      email: "atul@example.com",
      status: "unknown",
      roles: ["reader"],
    },
  ];

  try {
    validateSchema(validUser, userSchema);
    console.log("Valid user: ACCEPTED");
  } catch (error) {
    console.log("Valid user: REJECTED:", error.message);
  }

  invalidUsers.forEach((user, index) => {
    try {
      validateSchema(user, userSchema);
      console.log(`Invalid user ${index + 1}: ACCEPTED`);
    } catch (error) {
      console.log(
        `Invalid user ${index + 1}: REJECTED: ${error.message}`
      );
    }
  });
}

// -----------------------------------------------------------------------------
// 9. Documentation auditing
// -----------------------------------------------------------------------------

function auditDocumentation(document) {
  const issues = [];
  const operationIds = new Map();

  for (const { path, method, operation } of iterateOperations(document)) {
    const location = `${method.toUpperCase()} ${path}`;

    if (!operation.summary) {
      issues.push({
        severity: "warning",
        location,
        message: "Missing summary.",
      });
    }

    if (!operation.description) {
      issues.push({
        severity: "warning",
        location,
        message: "Missing description.",
      });
    }

    if (!operation.operationId) {
      issues.push({
        severity: "error",
        location,
        message: "Missing operationId.",
      });
    } else if (operationIds.has(operation.operationId)) {
      issues.push({
        severity: "error",
        location,
        message: `Duplicate operationId '${operation.operationId}'.`,
      });
    } else {
      operationIds.set(operation.operationId, location);
    }

    if (
      !operation.responses ||
      Object.keys(operation.responses).length === 0
    ) {
      issues.push({
        severity: "error",
        location,
        message: "No responses documented.",
      });
    }

    for (const [statusCode, response] of Object.entries(
      operation.responses || {}
    )) {
      if (
        response &&
        typeof response === "object" &&
        !response.$ref &&
        !response.description
      ) {
        issues.push({
          severity: "warning",
          location: `${location} -> ${statusCode}`,
          message: "Response is missing description.",
        });
      }
    }
  }

  return issues;
}

function demonstrateAudit(document) {
  printSection("6. Documentation audit");

  const issues = auditDocumentation(document);

  if (issues.length === 0) {
    console.log("No documentation quality issues found.");
    return;
  }

  issues.forEach((issue) => {
    console.log(
      `[${issue.severity.toUpperCase()}] ${issue.location}: ${issue.message}`
    );
  });
}

// -----------------------------------------------------------------------------
// 10. Swagger UI and ReDoc integration
// -----------------------------------------------------------------------------

function createSwaggerUiHtml(specUrl = "./openapi.json") {
  /*
   * Swagger UI reads the OpenAPI document and renders an interactive
   * reference page. The browser, rather than the JavaScript file itself,
   * performs the normal documentation rendering.
   */
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>User Management API - Swagger UI</title>
  <link rel="stylesheet"
        href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.onload = function () {
      SwaggerUIBundle({
        url: "${specUrl}",
        dom_id: "#swagger-ui"
      });
    };
  </script>
</body>
</html>`;
}

function createReDocHtml(specUrl = "./openapi.json") {
  /*
   * ReDoc emphasizes organized reference documentation and schema browsing.
   */
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>User Management API - ReDoc</title>
</head>
<body>
  <redoc spec-url="${specUrl}"></redoc>
  <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
</body>
</html>`;
}

function demonstrateDocumentationRenderers() {
  printSection("7. Swagger UI and ReDoc");

  const swaggerPage = createSwaggerUiHtml();
  const redocPage = createReDocHtml();

  console.log("Swagger UI page characters:", swaggerPage.length);
  console.log("ReDoc page characters:", redocPage.length);

  console.log("\nSwagger UI excerpt:");
  console.log(swaggerPage.slice(0, 350) + "...");

  console.log("\nReDoc excerpt:");
  console.log(redocPage.slice(0, 300) + "...");
}

// -----------------------------------------------------------------------------
// 11. Asynchronous loading
// -----------------------------------------------------------------------------

async function loadOpenApiDocument(document) {
  /*
   * Real applications commonly fetch an OpenAPI document over HTTP.
   * This function uses a Promise to model asynchronous loading while avoiding
   * network dependency in the study program.
   */
  return new Promise((resolve) => {
    setTimeout(() => resolve(document), 10);
  });
}

async function demonstrateAsyncDocumentationLoading(document) {
  printSection("8. Asynchronous OpenAPI loading");

  const loadedDocument = await loadOpenApiDocument(document);

  console.log(
    "Loaded specification:",
    loadedDocument.info.title,
    loadedDocument.info.version
  );
}

// -----------------------------------------------------------------------------
// 12. Contract-style API simulation
// -----------------------------------------------------------------------------

function simulateGetUser(userId) {
  if (!Number.isInteger(userId) || userId <= 0) {
    return {
      statusCode: 400,
      body: {
        code: "INVALID_USER_ID",
        message: "user_id must be a positive integer",
        details: {},
      },
    };
  }

  if (userId === 404) {
    return {
      statusCode: 404,
      body: {
        code: "USER_NOT_FOUND",
        message: "The requested user does not exist.",
        details: {},
      },
    };
  }

  return {
    statusCode: 200,
    body: {
      id: userId,
      name: "Example User",
      email: "example@example.com",
      status: "active",
      roles: ["reader"],
    },
  };
}

function demonstrateContractTesting(document) {
  printSection("9. Contract-style testing");

  const operation =
    document.paths["/users/{user_id}"].get;

  const responseSchemaReference =
    operation.responses["200"].content["application/json"].schema.$ref;

  const responseSchema = resolveLocalRef(
    document,
    responseSchemaReference
  );

  for (const userId of [101, 404, 0]) {
    const response = simulateGetUser(userId);

    console.log(
      `\nGET /users/${userId} -> HTTP ${response.statusCode}`
    );

    if (response.statusCode === 200) {
      try {
        validateSchema(response.body, responseSchema);
        console.log("Response matches the documented User schema.");
      } catch (error) {
        console.log("Schema mismatch:", error.message);
      }
    } else {
      console.log("Error response:");
      console.log(prettyJson(response.body));
    }
  }
}

// -----------------------------------------------------------------------------
// 13. Operation ID design
// -----------------------------------------------------------------------------

function demonstrateOperationIds() {
  printSection("10. operationId design");

  const goodIds = [
    "getUser",
    "listUsers",
    "createUser",
    "deleteUser",
    "getHealth",
  ];

  const problematicIds = [
    "get",
    "operation1",
    "GET /users",
    "user",
    "thing",
  ];

  console.log("Useful operationId properties:");
  console.log("  - unique");
  console.log("  - stable");
  console.log("  - descriptive");
  console.log("  - suitable for generated SDK method names");
  console.log("  - independent of presentation-layer wording");

  console.log("\nGood examples:");
  goodIds.forEach((id) => console.log(`  - ${id}`));

  console.log("\nPotentially weak examples:");
  problematicIds.forEach((id) => console.log(`  - ${id}`));
}

// -----------------------------------------------------------------------------
// 14. API metadata
// -----------------------------------------------------------------------------

function demonstrateMetadata(document) {
  printSection("11. API metadata");

  console.log("Title:", document.info.title);
  console.log("Version:", document.info.version);
  console.log("Description:", document.info.description);
  console.log("Contact:", document.info.contact.email);
  console.log("License:", document.info.license.name);

  console.log("\nWhy metadata matters:");
  console.log(
    "  Metadata gives documentation consumers enough context to identify the API contract."
  );
  console.log(
    "  API version is not the same thing as the OpenAPI specification version."
  );
}

// -----------------------------------------------------------------------------
// 15. Security documentation
// -----------------------------------------------------------------------------

function demonstrateSecurity(document) {
  printSection("12. Security schemes");

  console.log(
    prettyJson(document.components.securitySchemes)
  );

  console.log(
    "\nSecurity documentation explains how a client should authenticate."
  );
  console.log(
    "It does not itself enforce authentication at runtime."
  );

  const alternatives = {
    apiKey: {
      type: "apiKey",
      in: "header",
      name: "X-API-Key",
    },

    basic: {
      type: "http",
      scheme: "basic",
    },

    bearer: {
      type: "http",
      scheme: "bearer",
      bearerFormat: "JWT",
    },

    oauth2: {
      type: "oauth2",
      flows: {
        authorizationCode: {
          authorizationUrl: "https://example.com/oauth/authorize",
          tokenUrl: "https://example.com/oauth/token",
          scopes: {
            "users:read": "Read users",
            "users:write": "Modify users",
          },
        },
      },
    },
  };

  console.log("\nAlternative security scheme structures:");
  console.log(prettyJson(alternatives));
}

// -----------------------------------------------------------------------------
// 16. Edge cases and production considerations
// -----------------------------------------------------------------------------

function demonstrateEdgeCases() {
  printSection("13. Edge cases");

  const cases = [
    [
      "Duplicate operationId",
      "Can cause generated SDK method-name collisions.",
    ],
    [
      "Incorrect example",
      "Can teach API consumers to send payloads that violate the schema.",
    ],
    [
      "Missing error responses",
      "Leaves clients uncertain about failure formats and status codes.",
    ],
    [
      "Unstable operationId",
      "Can create unnecessary source-code changes in generated clients.",
    ],
    [
      "Missing path parameter",
      "A path variable such as {user_id} must have a matching path parameter.",
    ],
    [
      "Schema drift",
      "The implementation and specification can disagree even when the document itself parses.",
    ],
    [
      "Undocumented authentication",
      "Consumers may not understand how to obtain or send credentials.",
    ],
    [
      "Huge examples",
      "Large examples can make documentation slower and harder to read.",
    ],
    [
      "Secrets in examples",
      "Documentation can accidentally expose credentials or sensitive data.",
    ],
  ];

  cases.forEach(([name, explanation]) => {
    console.log(`${name}:`);
    console.log(`  ${explanation}`);
  });
}

function demonstrateProductionConsiderations() {
  printSection("14. Production considerations");

  const considerations = [
    "Keep the OpenAPI document version-controlled.",
    "Validate it in CI before deployment.",
    "Keep operationIds unique and stable.",
    "Reuse components with $ref.",
    "Keep examples consistent with schemas.",
    "Use HTTPS for production documentation and API traffic.",
    "Avoid exposing secrets or private infrastructure information.",
    "Pin documentation renderer versions where reproducibility matters.",
    "Decide carefully whether Try It Out should be available against production systems.",
    "Protect internal API documentation when the API itself is private.",
    "Review schema changes for backward compatibility.",
    "Generate documentation from API source definitions when practical.",
  ];

  considerations.forEach((item) => console.log(`- ${item}`));
}

// -----------------------------------------------------------------------------
// 17. Main
// -----------------------------------------------------------------------------

async function main() {
  explainTerminology();
  demonstrateSchemaTypes();

  const document = buildOpenApiDocument();

  inspectOperations(document);
  demonstrateRefs(document);
  demonstrateValidation(document);
  demonstrateAudit(document);
  demonstrateDocumentationRenderers();
  await demonstrateAsyncDocumentationLoading(document);
  demonstrateContractTesting(document);
  demonstrateOperationIds();
  demonstrateMetadata(document);
  demonstrateSecurity(document);
  demonstrateEdgeCases();
  demonstrateProductionConsiderations();

  printSection("15. Generated OpenAPI JSON");

  console.log(prettyJson(document));

  printSection("16. Basic document checks");

  const operationIds = [];

  for (const { path, method, operation } of iterateOperations(document)) {
    if (!operation.operationId) {
      throw new Error(
        `Missing operationId on ${method.toUpperCase()} ${path}`
      );
    }

    operationIds.push(operation.operationId);
  }

  const uniqueOperationIds = new Set(operationIds);

  console.log(
    "All operationIds unique:",
    uniqueOperationIds.size === operationIds.length
  );

  console.log(
    "Number of operations:",
    operationIds.length
  );

  console.log(
    "Number of reusable schemas:",
    Object.keys(document.components.schemas).length
  );

  console.log(
    "Number of reusable parameters:",
    Object.keys(document.components.parameters).length
  );

  console.log(
    "Number of reusable responses:",
    Object.keys(document.components.responses).length
  );

  printSection("17. End of study program");

  console.log(
    "The OpenAPI document is the contract consumed by documentation and tooling."
  );
  console.log(
    "Swagger UI and ReDoc present that contract differently, while schemas,"
  );
  console.log(
    "operationIds, metadata, examples, responses, and security definitions"
  );
  console.log(
    "make the contract useful to both humans and software."
  );
}

main().catch((error) => {
  console.error("Program failed:", error);
  process.exitCode = 1;
});
