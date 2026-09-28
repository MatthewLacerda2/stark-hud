import { describe, expect, it } from "vitest";
import { prepare } from "@/lib/hologram";

/**
 * A `.glb` built in memory: one triangle, and whatever nodes a test hangs off
 * it. Written here rather than committed as a file, so what it holds can be
 * read in the test that relies on it.
 */
function glb(nodes: object[], roots: number[]): ArrayBuffer {
  const triangle = new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]);
  const json = {
    asset: { version: "2.0" },
    scene: 0,
    scenes: [{ nodes: roots }],
    nodes,
    meshes: [{ primitives: [{ attributes: { POSITION: 0 } }] }],
    accessors: [
      {
        bufferView: 0,
        componentType: 5126,
        count: 3,
        type: "VEC3",
        min: [0, 0, 0],
        max: [1, 1, 0],
      },
    ],
    bufferViews: [{ buffer: 0, byteOffset: 0, byteLength: 36 }],
    buffers: [{ byteLength: 36 }],
  };
  const text = new TextEncoder().encode(JSON.stringify(json));
  const jsonLength = Math.ceil(text.length / 4) * 4;
  const binLength = triangle.byteLength;
  const out = new ArrayBuffer(12 + 8 + jsonLength + 8 + binLength);
  const view = new DataView(out);
  view.setUint32(0, 0x46546c67, true); // "glTF"
  view.setUint32(4, 2, true);
  view.setUint32(8, out.byteLength, true);
  view.setUint32(12, jsonLength, true);
  view.setUint32(16, 0x4e4f534a, true); // "JSON"
  const bytes = new Uint8Array(out);
  bytes.fill(0x20, 20, 20 + jsonLength);
  bytes.set(text, 20);
  view.setUint32(20 + jsonLength, binLength, true);
  view.setUint32(24 + jsonLength, 0x004e4942, true); // "BIN"
  bytes.set(new Uint8Array(triangle.buffer), 28 + jsonLength);
  return out;
}

describe("prepare", () => {
  it("finds every labelled node, in the file's order", async () => {
    const model = await prepare(
      glb(
        [
          {
            name: "body",
            mesh: 0,
            children: [1, 2],
            extras: { label: "body" },
          },
          { name: "a", translation: [1, 0, 0], extras: { label: "Paris" } },
          { name: "b", translation: [0, 1, 0], extras: { label: 5 } },
          { name: "c", translation: [0, 0, 1] },
        ],
        [0, 3],
      ),
      "gltf",
    );
    expect(model.labels.map(({ text }) => text)).toEqual([
      "body",
      "Paris",
      "5",
    ]);
    expect(model.labels.map(({ anchor }) => anchor.name)).toEqual([
      "body",
      "a",
      "b",
    ]);
  });

  it("finds none in a file that carries none", async () => {
    const model = await prepare(
      glb([{ name: "body", mesh: 0 }, { name: "c" }], [0, 1]),
      "gltf",
    );
    expect(model.labels).toEqual([]);
    expect(model.drawables).toHaveLength(1);
  });
});
