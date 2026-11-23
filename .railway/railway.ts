import { defineRailway, github, project, service } from "railway/iac";
// Keep PostgreSQL and Railway-managed variables outside this backend-only partial.
export const partial = "vocabulario";
export default defineRailway(() => {
  const vocabulario = service("vocabulario", {
    source: github("stepienov/vocabulario", { branch: "main", checkSuites: false, rootDirectory: "/backend" }),
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "Dockerfile" },
    deploy: { restartPolicyType: "ON_FAILURE", restartPolicyMaxRetries: 5 },
    healthcheck: "/health",
    healthcheckTimeout: 300,
    replicas: { "europe-west4-drams3a": 1 },
    domains: ["vocabulario.io"],
  });

  return project("vocabulario", {
    variables: { managed: false },
    resources: [vocabulario],
  });
});
