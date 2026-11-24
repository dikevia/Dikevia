// Local, browser-side embedding generation. The user's question is never sent to the model host.
import { env, pipeline } from "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.7.2";

env.allowLocalModels = false;
env.useBrowserCache = true;
if (env.backends?.onnx?.wasm) {
  env.backends.onnx.wasm.numThreads = 1;
}

const MODEL_ID = "Xenova/paraphrase-multilingual-MiniLM-L12-v2";
const SEGMENT_CHARS = 500;
const SEGMENT_OVERLAP = 60;
let extractorPromise = null;

function splitForEmbedding(value) {
  const text = String(value || "").normalize("NFC").trim();
  if (!text) return [];
  const segments = [];
  let start = 0;
  while (start < text.length) {
    let end = Math.min(text.length, start + SEGMENT_CHARS);
    if (end < text.length) {
      const midpoint = start + Math.floor(SEGMENT_CHARS / 2);
      const newline = text.lastIndexOf("\n", end - 1);
      const sentence = text.lastIndexOf(". ", end - 1);
      const boundary = Math.max(newline >= midpoint ? newline : -1, sentence >= midpoint ? sentence : -1);
      if (boundary > start) end = boundary + 1;
    }
    const piece = text.slice(start, end).replace(/\s+/gu, " ").trim();
    if (piece) segments.push(piece);
    if (end >= text.length) break;
    start = Math.max(start + 1, end - SEGMENT_OVERLAP);
  }
  return segments;
}

function normalizedMean(vectors) {
  if (!vectors.length) throw new Error("Aucun segment vectorisé.");
  const dimensions = vectors[0].length;
  if (dimensions !== 384 || vectors.some(vector => vector.length !== dimensions)) {
    throw new Error("Dimensions incohérentes entre les segments.");
  }
  const mean = Array.from({ length: dimensions }, (_, index) =>
    vectors.reduce((sum, vector) => sum + vector[index], 0) / vectors.length
  );
  const norm = Math.sqrt(mean.reduce((sum, value) => sum + value * value, 0));
  if (!Number.isFinite(norm) || norm === 0 || mean.some(value => !Number.isFinite(value))) {
    throw new Error("Le modèle a produit un vecteur invalide.");
  }
  return mean.map(value => value / norm);
}

self.onmessage = async (event) => {
  const { id, text } = event.data || {};
  if (!Number.isInteger(id) || typeof text !== "string" || !text.trim()) {
    self.postMessage({ id, error: "Requête d'embedding invalide." });
    return;
  }
  try {
    if (!extractorPromise) {
      extractorPromise = pipeline("feature-extraction", MODEL_ID, { quantized: true });
    }
    const extractor = await extractorPromise;
    const segments = splitForEmbedding(text.slice(0, 5000));
    const vectors = [];
    for (const segment of segments) {
      // FastEmbed uses mean pooling without per-segment normalization for this model.
      // Normalize only after aggregating all segments, matching the corpus pipeline.
      const output = await extractor(segment, { pooling: "mean", normalize: false });
      vectors.push(Array.from(output.data, Number));
    }
    const embedding = normalizedMean(vectors);
    if (embedding.some(value => !Number.isFinite(value))) {
      throw new Error("Le modèle n'a pas produit un vecteur valide.");
    }
    self.postMessage({ id, embedding });
  } catch (error) {
    extractorPromise = null;
    self.postMessage({
      id,
      error: String(error?.message || error || "Erreur du modèle local."),
    });
  }
};
