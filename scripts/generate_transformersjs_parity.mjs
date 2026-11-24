#!/usr/bin/env node
/**
 * Generate Transformers.js vectors in Node for the isolated parity workflow.
 * Uses the same model, segmentation, pooling and aggregation as the browser worker.
 */
import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { env, pipeline } from "@huggingface/transformers";

const MODEL = "Xenova/paraphrase-multilingual-MiniLM-L12-v2";
const DIMENSIONS = 384;
const MAX_QUERY_CHARS = 5000;
env.allowLocalModels = false;
env.useBrowserCache = false;
if (env.backends?.onnx?.wasm) env.backends.onnx.wasm.numThreads = 1;

function split(value) {
  const text = String(value || "").normalize("NFC").slice(0, MAX_QUERY_CHARS).trim();
  if (!text) return [];
  const segments = [];
  let start = 0;
  while (start < text.length) {
    let end = Math.min(text.length, start + 500);
    if (end < text.length) {
      const midpoint = start + 250;
      const newline = text.lastIndexOf("\n", end - 1);
      const sentence = text.lastIndexOf(". ", end - 1);
      const boundary = Math.max(newline >= midpoint ? newline : -1, sentence >= midpoint ? sentence : -1);
      if (boundary > start) end = boundary + 1;
    }
    const piece = text.slice(start, end).replace(/\s+/gu, " ").trim();
    if (piece) segments.push(piece);
    if (end >= text.length) break;
    start = Math.max(start + 1, end - 60);
  }
  return segments;
}

function normalizedMean(vectors) {
  if (!vectors.length || vectors.some(vector => vector.length !== DIMENSIONS)) {
    throw new Error("Nombre de segments ou dimension du modèle inattendu.");
  }
  const mean = Array.from({ length: DIMENSIONS }, (_, index) =>
    vectors.reduce((sum, vector) => sum + vector[index], 0) / vectors.length
  );
  const norm = Math.sqrt(mean.reduce((sum, value) => sum + value * value, 0));
  if (!Number.isFinite(norm) || norm === 0 || mean.some(value => !Number.isFinite(value))) {
    throw new Error("Le modèle a produit un vecteur invalide.");
  }
  return mean.map(value => value / norm);
}

function hash(text) {
  return createHash("sha256").update(text.normalize("NFC").slice(0, MAX_QUERY_CHARS), "utf8").digest("hex");
}

const [inputPath, outputPath] = process.argv.slice(2);
if (!inputPath || !outputPath) {
  throw new Error("Usage: node scripts/generate_transformersjs_parity.mjs <input.json> <output.json>");
}
const input = JSON.parse(await readFile(inputPath, "utf8"));
if (!Array.isArray(input.items) || input.items.length === 0) throw new Error("Jeu de questions vide.");
const ids = new Set();
for (const item of input.items) {
  if (!item || typeof item.id !== "string" || !item.id.trim() || ids.has(item.id) ||
      typeof item.text !== "string" || !item.text.trim()) {
    throw new Error("Entrée invalide ou identifiant dupliqué.");
  }
  ids.add(item.id);
}
console.log("Chargement du modèle Transformers.js…");
const extractor = await pipeline("feature-extraction", MODEL, { quantized: false });
const items = [];
for (const [index, item] of input.items.entries()) {
  console.log(`Transformers.js ${index + 1}/${input.items.length}: ${item.id}`);
  const vectors = [];
  for (const segment of split(item.text)) {
    const result = await extractor(segment, { pooling: "mean", normalize: false });
    vectors.push(Array.from(result.data, Number));
  }
  items.push({
    id: item.id,
    text: item.text,
    text_sha256: hash(item.text),
    embedding: normalizedMean(vectors),
  });
}
const output = {
  engine: "transformers.js",
  model: MODEL,
  dimensions: DIMENSIONS,
  transformers_js_version: "3.7.2",
  quantized: false,
  execution: "node-github-actions",
  items,
};
await writeFile(outputPath, JSON.stringify(output, null, 2) + "\n", "utf8");
console.log(`Export Transformers.js écrit : ${outputPath}`);
