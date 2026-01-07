import React, { useState } from "react";
import { createVendor } from "../api";   // ✅ fix import

function VendorForm({ onVendorCreated }) {
  const [form, setForm] = useState({ name: "", contact: "", phone: "" });

  const handleSubmit = async (e) => {
    e.preventDefault();
    const newVendor = await createVendor(form);
    onVendorCreated(newVendor);
    setForm({ name: "", contact: "", phone: "" });
  };

  return (
    <form onSubmit={handleSubmit}>
      <h3>Create Vendor</h3>
      <input
        type="text"
        placeholder="Name"
        value={form.name}
        onChange={(e) => setForm({ ...form, name: e.target.value })}
      />
      <input
        type="text"
        placeholder="Contact"
        value={form.contact}
        onChange={(e) => setForm({ ...form, contact: e.target.value })}
      />
      <input
        type="text"
        placeholder="Phone"
        value={form.phone}
        onChange={(e) => setForm({ ...form, phone: e.target.value })}
      />
      <button type="submit">Add Vendor</button>
    </form>
  );
}

export default VendorForm;
