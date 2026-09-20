import { createTester } from "./tester";
import { noHandBuiltApiUrl } from "./no-hand-built-api-url";

const tester = createTester();

// The rule carries no path test of its own: `eslint.config.ts` points it at
// everything except `lib/api/` and the tests, the same block that already says
// pages never fetch. So these fixtures are only about the shape of the string.
const FILE = "/repo/frontend/src/components/board/items/list.tsx";

tester.run("no-hand-built-api-url", noHandBuiltApiUrl, {
  valid: [
    { filename: FILE, code: `const x = <img src={iconUrl(id)} />;` },
    { filename: FILE, code: `const x = <img src={iconUrl(id, i)} />;` },
    // A path with no base is what a `lib/api/` module passes to `request()`.
    { filename: FILE, code: `const x = request("/board/items");` },
    // Prose is allowed to name it — this whole rule is about strings.
    { filename: FILE, code: `// client.ts owns /api/v1\nconst x = 1;` },
    { filename: FILE, code: `const x = "/api/v2/media";` },
  ],
  invalid: [
    {
      filename: FILE,
      code: `const x = <video src="/api/v1/media/background" />;`,
      errors: [{ messageId: "built" }],
    },
    // How all but one of them were actually written.
    {
      filename: FILE,
      code: "const x = <img src={`/api/v1/media/${id}/icon`} />;",
      errors: [{ messageId: "built" }],
    },
    {
      filename: FILE,
      code: "const url = `/api/v1/media/${id}/track/${index}${part}`;",
      errors: [{ messageId: "built" }],
    },
  ],
});
