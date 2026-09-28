// A thin typed client. Every type here comes from the generated schema (npm run gen:api).
import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

type Schemas = components["schemas"];
export type TurnView = Schemas["TurnView"];
export type QuestionView = Schemas["QuestionView"];
export type ActionView = Schemas["ActionView"];
export type ReviewView = Schemas["ReviewView"];
export type ErrorBody = Schemas["ErrorBody"];
export type SessionView = Schemas["SessionView"];
export type UiText = Schemas["UiText"];
export type ResumeCodeView = Schemas["ResumeCodeView"];
export type HelpView = Schemas["HelpView"];
export type StaffSummary = Schemas["StaffSummary"];
export type BenefitSummary = Schemas["BenefitSummary"];
export type ReplyCommand = Schemas["ReplyRequest"]["command"];

export const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/** A failed request. `body` is the API's fixed ErrorBody, or null if the API was not reached. */
export class ApiFailure extends Error {
  constructor(
    readonly body: ErrorBody | null,
    readonly status: number,
  ) {
    super(body?.code ?? "no_connection");
  }
}

const client = createClient<paths>({ baseUrl: API_URL });

type Result<T> = { data?: T; error?: unknown; response: Response };

async function call<T>(request: Promise<Result<T>>): Promise<T> {
  let result: Result<T>;
  try {
    result = await request;
  } catch {
    throw new ApiFailure(null, 0);
  }
  if (result.data === undefined) {
    throw new ApiFailure((result.error as ErrorBody | undefined) ?? null, result.response.status);
  }
  return result.data;
}

export interface Session {
  id: string;
  token: string;
}

const auth = (s: Session) => ({
  params: { path: { intake_id: s.id }, header: { "x-intake-token": s.token } },
});

export const api = {
  uiText: () => call(client.GET("/ui/text")),
  help: () => call(client.GET("/help/person")),
  create: () => call(client.POST("/intakes")),
  resumeWithCode: (resume_code: string) =>
    call(client.POST("/intakes/resume", { body: { resume_code } })),
  get: (s: Session) => call(client.GET("/intakes/{intake_id}", auth(s))),
  start: (s: Session, turn: number) =>
    call(client.POST("/intakes/{intake_id}/start", { ...auth(s), body: { turn } })),
  reply: (s: Session, turn: number, command: ReplyCommand) =>
    call(client.POST("/intakes/{intake_id}/replies", { ...auth(s), body: { turn, command } })),
  pause: (s: Session, turn: number) =>
    call(client.POST("/intakes/{intake_id}/pause", { ...auth(s), body: { turn } })),
  resume: (s: Session, turn: number) =>
    call(client.POST("/intakes/{intake_id}/resume", { ...auth(s), body: { turn } })),
  resumeCode: (s: Session) => call(client.POST("/intakes/{intake_id}/resume-code", auth(s))),
  edit: (s: Session, turn: number, field_id: string) =>
    call(client.POST("/intakes/{intake_id}/review/edit", { ...auth(s), body: { turn, field_id } })),
  submit: (s: Session, turn: number) =>
    call(client.POST("/intakes/{intake_id}/submit", { ...auth(s), body: { turn } })),
  email: (s: Session, key: string) =>
    call(
      client.POST("/intakes/{intake_id}/email", {
        params: {
          path: { intake_id: s.id },
          header: { "x-intake-token": s.token, "idempotency-key": key },
        },
      }),
    ),
  staffSummary: (s: Session) => call(client.POST("/intakes/{intake_id}/staff-summary", auth(s))),
  benefitSummary: (s: Session) =>
    call(client.POST("/intakes/{intake_id}/benefit-summary", auth(s))),
};
