// Local, browser-side embedding generation. The user's question is never sent to the model host.
import { env, pipeline } from "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.7.2";

env.allowLocalModels = false;
env.useBrowserCache = true;
if (env.backends?.onnx?.wasm) {
  env.backends.onnx.wasm.numThreads = 1;
}

const MODEL_ID = "Xenova/paraphrase-multilingual-MiniLM-L12-v2";
let extractorPromise = null;

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
    const output = await extractor(text.slice(0, 5000), {
      pooling: "mean",
      normalize: true,
    });
    const embedding = Array.from(output.data, Number);
    if (embedding.length !== 384 || embedding.some((value) => !Number.isFinite(value))) {
      throw new Error("Le modèle n'a pas produit un vecteur valide de 384 dimensions.");
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
