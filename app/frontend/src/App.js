// src/App.js
import React, { useEffect, useState } from "react";
import {
  fetchProducts,
  fetchVendors,
  createProduct,
  createVendor,
  deleteProduct,
  deleteVendor,
} from "./api";
import {
  Moon,
  Sun,
  Trash2,
  Upload,
  PlusCircle,
  FileDown,
  DownloadCloud,
} from "lucide-react";

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [products, setProducts] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [darkMode, setDarkMode] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [previewRows, setPreviewRows] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const [manufacturerOverride, setManufacturerOverride] = useState("");
  const [forceManufacturer, setForceManufacturer] = useState(false);
  const [vendorName, setVendorName] = useState("");
  const [productForm, setProductForm] = useState({
    style: "",
    color: "",
    sku: "",
    product_type: "",
    pricing_unit: "EA",
    price: "",
    width: "",
    backing: "",
    is_promo: false,
    display_online: true,
    vendor_id: "",
  });

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    try {
      const p = await fetchProducts();
      const v = await fetchVendors();
      setProducts(p);
      setVendors(v);
    } catch (e) {
      console.error(e);
    }
  }

  async function handleCreateVendor() {
    if (!vendorName.trim()) return alert("Enter vendor name");
    await createVendor({ name: vendorName.trim() });
    setVendorName("");
    loadData();
  }

  async function handleCreateProduct() {
    if (!productForm.style || !productForm.vendor_id) return alert("Style and vendor required");
    await createProduct(productForm);
    setProductForm({
      style: "",
      color: "",
      sku: "",
      product_type: "",
      pricing_unit: "EA",
      price: "",
      width: "",
      backing: "",
      is_promo: false,
      display_online: true,
      vendor_id: "",
    });
    loadData();
  }

  async function confirmAndDeleteProduct(id) {
    if (!window.confirm("Delete this product?")) return;
    await deleteProduct(id);
    loadData();
  }

  async function confirmAndDeleteVendor(id) {
    if (!window.confirm("Delete this vendor?")) return;
    await deleteVendor(id);
    loadData();
  }

  function toggleDark() {
    setDarkMode((d) => !d);
  }

  // Import B2B CSV -> POST to backend
  async function handleImportB2B(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    setUploading(true);
    try {
      const res = await fetch(`${API_URL}/b2b/import/csv`, { method: "POST", body: fd });
      if (!res.ok) throw new Error("Import failed");
      alert("✅ Imported B2B CSV");
      loadData();
    } catch (err) {
      console.error(err);
      alert("❌ Failed to import. See backend logs.");
    } finally {
      setUploading(false);
      e.target.value = null;
    }
  }

  // Preview conversion -> shows preview modal
  async function handlePreviewConvert(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const fd = new FormData();
    fd.append("file", file);
    // attach manufacturer override and force (so preview can show intended result)
    if (manufacturerOverride) fd.append("manufacturer", manufacturerOverride);
    fd.append("force_manufacturer", forceManufacturer ? "true" : "false");

    try {
      const res = await fetch(`${API_URL}/b2b/preview`, { method: "POST", body: fd });
      if (!res.ok) throw new Error("Preview failed");
      const data = await res.json();
      if (data.already_b2b) {
        alert("This file is already in B2B format — previewing first rows.");
        setPreviewRows(data.sample || []);
      } else {
        setPreviewRows(data.rows_preview || []);
      }
      setShowPreview(true);
    } catch (err) {
      console.error(err);
      alert("❌ Preview failed. Check backend logs.");
    } finally {
      setUploading(false);
      e.target.value = null;
    }
  }

  // Convert and download CSV (uses manufacturerOverride + forceManufacturer)
  async function handleConvertAndDownload(file) {
    if (!file) return;
    setUploading(true);
    const fd = new FormData();
    fd.append("file", file);
    if (manufacturerOverride) fd.append("manufacturer", manufacturerOverride);
    fd.append("force_manufacturer", forceManufacturer ? "true" : "false");

    try {
      const res = await fetch(`${API_URL}/b2b/convert-to-b2b`, { method: "POST", body: fd });
      if (!res.ok) throw new Error("Convert failed");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "converted_b2b.csv";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      alert("✅ Converted and downloaded.");
      setShowPreview(false);
      setPreviewRows(null);
    } catch (err) {
      console.error(err);
      alert("❌ Convert failed. See backend logs.");
    } finally {
      setUploading(false);
    }
  }

  // convenience: convert using previously selected file -> we'll re-open file dialog
  function handleConvertInputClick() {
    document.getElementById("convert-file-input")?.click();
  }

  async function handleExportJSON() {
    try {
      const res = await fetch(`${API_URL}/b2b/export/json`);
      if (!res.ok) throw new Error("Export failed");
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "b2b_products.json";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
      alert("❌ Export failed.");
    }
  }

  return (
    <div className={`${darkMode ? "dark" : ""}`}>
      <div className={`min-h-screen ${darkMode ? "bg-gray-900 text-gray-100" : "bg-gray-50 text-gray-900"}`}>
        <div className="max-w-6xl mx-auto py-6 px-4">
          <header className="flex justify-between items-center mb-6">
            <h1 className="text-3xl font-bold">Floor Pricing Manager</h1>
            <div className="flex items-center gap-3">
              <button
                onClick={toggleDark}
                className="p-2 rounded bg-gray-200 dark:bg-gray-800"
                aria-label="toggle dark mode"
              >
                {darkMode ? <Sun size={18} /> : <Moon size={18} />}
              </button>
            </div>
          </header>

          {/* Vendors */}
          <section className="bg-white dark:bg-gray-800 rounded shadow p-4 mb-6">
            <h2 className="text-xl font-semibold mb-3">Vendors</h2>
            <div className="flex gap-2 mb-3">
              <input
                value={vendorName}
                onChange={(e) => setVendorName(e.target.value)}
                placeholder="Vendor name"
                className="flex-1 p-2 border rounded dark:bg-gray-700"
              />
              <button onClick={handleCreateVendor} className="px-4 py-2 bg-blue-600 text-white rounded flex items-center gap-2">
                <PlusCircle size={16} /> Add
              </button>
            </div>
            <ul className="space-y-2">
              {vendors.map((v) => (
                <li key={v.id} className="flex justify-between items-center p-2 bg-gray-100 dark:bg-gray-700 rounded">
                  <span>{v.name}</span>
                  <button onClick={() => confirmAndDeleteVendor(v.id)} className="text-red-500">
                    <Trash2 size={16} />
                  </button>
                </li>
              ))}
            </ul>
          </section>

          {/* Add Product */}
          <section className="bg-white dark:bg-gray-800 rounded shadow p-4 mb-6">
            <h2 className="text-xl font-semibold mb-3">Add Product</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <input className="p-2 border rounded dark:bg-gray-700" placeholder="Style" value={productForm.style} onChange={(e)=>setProductForm({...productForm, style:e.target.value})} />
              <input className="p-2 border rounded dark:bg-gray-700" placeholder="Color" value={productForm.color} onChange={(e)=>setProductForm({...productForm, color:e.target.value})} />
              <input className="p-2 border rounded dark:bg-gray-700" placeholder="SKU" value={productForm.sku} onChange={(e)=>setProductForm({...productForm, sku:e.target.value})} />
              <input className="p-2 border rounded dark:bg-gray-700" placeholder="Product Type" value={productForm.product_type} onChange={(e)=>setProductForm({...productForm, product_type:e.target.value})} />
              <select className="p-2 border rounded dark:bg-gray-700" value={productForm.pricing_unit} onChange={(e)=>setProductForm({...productForm, pricing_unit:e.target.value})}>
                <option value="EA">EA</option>
                <option value="SF">SF</option>
                <option value="SY">SY</option>
                <option value="LF">LF</option>
                <option value="CT">CT</option>
              </select>
              <input className="p-2 border rounded dark:bg-gray-700" placeholder="Price" type="number" value={productForm.price} onChange={(e)=>setProductForm({...productForm, price:e.target.value})} />
              <input className="p-2 border rounded dark:bg-gray-700" placeholder="Width" type="number" value={productForm.width} onChange={(e)=>setProductForm({...productForm, width:e.target.value})} />
              <input className="p-2 border rounded dark:bg-gray-700" placeholder="Backing" value={productForm.backing} onChange={(e)=>setProductForm({...productForm, backing:e.target.value})} />
              <select className="p-2 border rounded dark:bg-gray-700" value={productForm.vendor_id} onChange={(e)=>setProductForm({...productForm, vendor_id:e.target.value})}>
                <option value="">Select Vendor</option>
                {vendors.map(v=> <option key={v.id} value={v.id}>{v.name}</option>)}
              </select>
            </div>
            <div className="mt-3 flex gap-2">
              <button onClick={handleCreateProduct} className="px-4 py-2 bg-green-600 text-white rounded flex items-center gap-2"><PlusCircle size={16}/> Add Product</button>
            </div>
          </section>

          {/* Product List */}
          <section className="bg-white dark:bg-gray-800 rounded shadow p-4 mb-6">
            <h2 className="text-xl font-semibold mb-3">Products</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b dark:border-gray-700">
                    <th className="py-2">Style</th>
                    <th>Color</th>
                    <th>SKU</th>
                    <th>Vendor</th>
                    <th>Price</th>
                    <th>Unit</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {products.map(p => (
                    <tr key={p.id} className="border-b dark:border-gray-700">
                      <td className="py-2">{p.style}</td>
                      <td>{p.color}</td>
                      <td>{p.sku}</td>
                      <td>{p.vendor?.name}</td>
                      <td>${(p.price || 0).toFixed(2)}</td>
                      <td>{p.pricing_unit || "EA"}</td>
                      <td className="text-right"><button onClick={()=>confirmAndDeleteProduct(p.id)} className="text-red-500"><Trash2 size={16}/></button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Import / Convert controls */}
          <section className="bg-white dark:bg-gray-800 rounded shadow p-4 mb-6">
            <div className="flex flex-wrap items-center gap-3 justify-between">
              <div className="flex gap-2 items-center">
                <label className="bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded flex items-center gap-2 cursor-pointer">
                  <Upload size={16}/> Import B2B CSV
                  <input type="file" accept=".csv" onChange={handleImportB2B} hidden />
                </label>

                {/* Preview (calls /b2b/preview) */}
                <label className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded flex items-center gap-2 cursor-pointer">
                  <Upload size={16}/> Preview & Convert
                  <input type="file" accept=".csv" onChange={handlePreviewConvert} hidden />
                </label>

                <input id="convert-file-input" type="file" accept=".csv" onChange={(e)=>handleConvertAndDownload(e.target.files?.[0])} style={{display:"none"}} />
              </div>

              <div className="flex gap-2 items-center">
                <input value={manufacturerOverride} onChange={(e)=>setManufacturerOverride(e.target.value)} placeholder="Manufacturer override (optional)" className="p-2 border rounded dark:bg-gray-700" />
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={forceManufacturer} onChange={(e)=>setForceManufacturer(e.target.checked)} />
                  Force Manufacturer
                </label>
                <button onClick={handleExportJSON} className="px-4 py-2 bg-green-600 text-white rounded flex items-center gap-2"><FileDown size={16}/> Export JSON</button>
              </div>
            </div>

            {uploading && <p className="mt-3 text-yellow-400">Processing...</p>}
          </section>

          {/* Preview modal */}
          {showPreview && (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
              <div className="bg-white dark:bg-gray-800 rounded shadow-lg w-full max-w-4xl p-4 overflow-auto">
                <h3 className="text-lg font-semibold mb-3">Preview converted rows (first 200)</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b dark:border-gray-700">
                        <th className="py-2">Manufacturer</th>
                        <th>Style</th>
                        <th>Color</th>
                        <th>SKU</th>
                        <th>Product Type</th>
                        <th>Unit</th>
                        <th>Cut Cost</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(previewRows || []).map((r, i) => (
                        <tr key={i} className="border-b dark:border-gray-700">
                          <td className="py-1">{r["~~Manufacturer"] || manufacturerOverride || "—"}</td>
                          <td>{r["Style Name"]}</td>
                          <td>{r["Color Name"]}</td>
                          <td>{r["SKU"]}</td>
                          <td>{r["Product Type"]}</td>
                          <td>{r["Pricing Unit"]}</td>
                          <td>{r["Cut Cost"]}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="mt-4 flex justify-end gap-2">
                  <button onClick={()=>{ setShowPreview(false); setPreviewRows(null); }} className="px-3 py-2 rounded border">Close</button>

                  <label className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-2 rounded flex items-center gap-2 cursor-pointer">
                    <DownloadCloud size={16}/> Convert & Download
                    {/* a hidden input for the actual convert+download */}
                    <input type="file" accept=".csv" onChange={(e)=> {
                      const file = e.target.files?.[0];
                      if (file) handleConvertAndDownload(file);
                    }} hidden />
                  </label>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
