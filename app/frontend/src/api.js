// src/api.js
const API_URL = "http://127.0.0.1:8000";

export async function fetchVendors() {
  const res = await fetch(`${API_URL}/vendors/`);
  if (!res.ok) throw new Error("Failed to fetch vendors");
  return await res.json();
}
export async function fetchProducts() {
  const res = await fetch(`${API_URL}/products/`);
  if (!res.ok) throw new Error("Failed to fetch products");
  return await res.json();
}
export async function createVendor(vendor) {
  const res = await fetch(`${API_URL}/vendors/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(vendor),
  });
  if (!res.ok) throw new Error("Failed to create vendor");
  return await res.json();
}
export async function createProduct(product) {
  const res = await fetch(`${API_URL}/products/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(product),
  });
  if (!res.ok) throw new Error("Failed to create product");
  return await res.json();
}
export async function deleteProduct(id) {
  const res = await fetch(`${API_URL}/products/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete product");
}
export async function deleteVendor(id) {
  const res = await fetch(`${API_URL}/vendors/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete vendor");
}

export async function deleteAllProducts() {
  const res = await fetch("http://127.0.0.1:8000/products/clear-all", {
    method: "DELETE",
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text);
  }
}

