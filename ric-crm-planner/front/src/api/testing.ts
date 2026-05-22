import client from "./client";

interface TestingSSOLinkResponse {
  url: string;
  ticket: string;
  expiresIn: number;
}

export async function createTestingSSOLink(applicationId?: number) {
  const body = typeof applicationId === "number" ? { application_id: applicationId } : {};
  return client.post<TestingSSOLinkResponse>("/api/users/integration/testing/sso-link/", body);
}
