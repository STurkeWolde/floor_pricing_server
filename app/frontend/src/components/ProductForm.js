import React, { useState } from "react";
import { createProduct } from "../api";   // ✅ fix import

function ProductForm({ onProductCreated, vendors }) {
  const [form, setForm] = useState({
    sku: "",
    style: "",
    color: "",
    product_type: "",
    pricing_unit: "",
    price: "",
    vendor_id: "",
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    const newProduct = await createProduct({ ...form, price: parseFloat(form.price) });
    onProductCreated(newProduct);
    setForm({ sku: "", style: "", color: "", product_type: "", pricing_unit: "", price: "", vendor_id: "" });
  };

  return (
    <form onSubmit={handleSubmit}>
      <h3>Create Product</h3>
      <input
        type="text"
        placeholder="SKU"
        value={form.sku}
        onChange={(e) => setForm({ ...form, sku: e.target.value })}
      />
      <input
        type="text"
        placeholder="Style"
        value={form.style}
        onChange={(e) => setForm({ ...form, style: e.target.value })}
      />
      <input
        type="text"
        placeholder="Color"
        value={form.color}
        onChange={(e) => setForm({ ...form, color: e.target.value })}
      />
      <input
        type="text"
        placeholder="Product Type"
        value={form.product_type}
        onChange={(e) => setForm({ ...form, product_type: e.target.value })}
      />
      <input
        type="text"
        placeholder="Pricing Unit"
        value={form.pricing_unit}
        onChange={(e) => setForm({ ...form, pricing_unit: e.target.value })}
      />
      <input
        type="number"
        placeholder="Price"
        value={form.price}
        onChange={(e) => setForm({ ...form, price: e.target.value })}
      />
      <select
        value={form.vendor_id}
        onChange={(e) => setForm({ ...form, vendor_id: e.target.value })}
      >
        <option value="">Select Vendor</option>
        {vendors.map((v) => (
          <option key={v.id} value={v.id}>
            {v.name}
          </option>
        ))}
      </select>
      <button type="submit">Add Product</button>
    </form>
  );
}

export default ProductForm;

