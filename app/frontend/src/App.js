import React, { useEffect, useState, useRef } from "react";
import {
  fetchProducts,
  fetchVendors,
  createProduct,
  createVendor,
  deleteProduct,
  deleteVendor,
  deleteAllProducts
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
  const [lastFile, setLastFile] = useState(null);

  const [vendorName, setVendorName] = useState("");
  const [productForm, setProductForm] = useState({
    style: "",
    color: "",
    sku: "",
    product_type: "",
    pricing_unit: "EA",
    price: "",
    vendor_id: "",
  });

  const convertInputRef = useRef();

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    const p = await fetchProducts();
    const v = await fetchVendors();
    setProducts(p);
    setVendors(v);
  }

  async function handleCreateVendor() {
    if (!vendorName.trim()) return alert("Enter vendor name");
    await createVendor({ name: vendorName.trim() });
    setVendorName("");
    loadData();
  }

  async function handleCreateProduct() {
    if (!productForm.style || !productForm.vendor_id)
      return alert("Style and vendor required");
    await createProduct(productForm);
    setProductForm({
      style: "",
      color: "",
      sku: "",
      product_type: "",
      pricing_unit: "EA",
      price: "",
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

  // ---------------- IMPORT ----------------

  async function handleImportB2B(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    setUploading(true);
    try {
      const res = await fetch(`${API_URL}/b2b/import/csv`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) throw new Error();
      alert("✅ Imported B2B CSV");
      loadData();
    } catch {
      alert("❌ Import failed");
    } finally {
      setUploading(false);
      e.target.value = null;
    }
  }

  // ---------------- PREVIEW ----------------

  async function handlePreviewConvert(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setLastFile(file);

    const fd = new FormData();
    fd.append("file", file);
    if (manufacturerOverride) fd.append("manufacturer", manufacturerOverride);
    fd.append("force_manufacturer", forceManufacturer ? "true" : "false");

    setUploading(true);
    try {
      const res = await fetch(`${API_URL}/b2b/preview`, {
        method: "POST",
        body: fd,
      });
      const data = await res.json();
      setPreviewRows(data.rows_preview || data.sample || []);
      setShowPreview(true);
    } catch {
      alert("❌ Preview failed");
    } finally {
      setUploading(false);
      e.target.value = null;
    }
  }

  // ---------------- CONVERT + DOWNLOAD ----------------

  async function handleConvertAndDownload(file) {
    if (!file) return;

    const fd = new FormData();
    fd.append("file", file);
    if (manufacturerOverride) fd.append("manufacturer", manufacturerOverride);
    fd.append("force_manufacturer", forceManufacturer ? "true" : "false");

    setUploading(true);
    try {
      const res = await fetch(`${API_URL}/b2b/convert-to-b2b`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) throw new Error();

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = url;
      a.download = "converted_b2b.csv";
      document.body.appendChild(a);
      a.click();
      a.remove();

      window.URL.revokeObjectURL(url);

      setShowPreview(false);
      setPreviewRows(null);
      alert("✅ Converted & downloaded");
    } catch {
      alert("❌ Convert failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleExportJSON() {
    const res = await fetch(`${API_URL}/b2b/export/json`);
    const data = await res.json();
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "b2b_products.json";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  }

  async function handleDeleteAllProducts() {
  if (!window.confirm("⚠️ Delete ALL products? This cannot be undone.")) return;
  await deleteAllProducts();
  loadData();
  alert("✅ All products deleted");
}



  return (
    <div className={darkMode ? "dark" : ""}>
      <div className={`min-h-screen ${darkMode ? "bg-gray-900 text-gray-100" : "bg-gray-50 text-gray-900"}`}>
        <div className="max-w-6xl mx-auto py-6 px-4">

          <header className="flex justify-between items-center mb-6">
            <h1 className="text-3xl font-bold">Floor Pricing Manager</h1>
            <button onClick={toggleDark} className="p-2 rounded bg-gray-200 dark:bg-gray-800">
              {darkMode ? <Sun size={18} /> : <Moon size={18} />}
            </button>
          </header>

          {/* Vendors */}
          <section className="bg-white dark:bg-gray-800 p-4 rounded mb-6">
            <h2 className="text-xl mb-3">Vendors</h2>
            <div className="flex gap-2 mb-3">
              <input className="flex-1 p-2 border rounded" value={vendorName} onChange={(e)=>setVendorName(e.target.value)} />
              <button onClick={handleCreateVendor} className="bg-blue-600 text-white px-3 py-2 rounded flex gap-1 items-center">
                <PlusCircle size={16}/> Add
              </button>
            </div>
            {vendors.map(v=>(
              <div key={v.id} className="flex justify-between bg-gray-100 dark:bg-gray-700 p-2 rounded mb-1">
                {v.name}
                <button onClick={()=>confirmAndDeleteVendor(v.id)}><Trash2 size={16}/></button>
              </div>
            ))}
          </section>

          {/* Products */}
<section className="bg-white dark:bg-gray-800 p-4 rounded mb-6">

  <div className="flex justify-between items-center mb-3">
    <h2 className="text-xl">Products</h2>

    <button
      onClick={handleDeleteAllProducts}
      className="bg-red-600 text-white px-3 py-2 rounded flex items-center gap-1 hover:bg-red-700"
    >
      <Trash2 size={16} />
      Delete All
    </button>
  </div>

  <table className="w-full text-sm">
    <thead>
      <tr>
        <th>Style</th>
        <th>SKU</th>
        <th>Vendor</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {products.map(p => (
        <tr key={p.id}>
          <td>{p.style}</td>
          <td>{p.sku}</td>
          <td>{p.vendor?.name}</td>
          <td>
            <button onClick={() => confirmAndDeleteProduct(p.id)}>
              <Trash2 size={14}/>
            </button>
          </td>
        </tr>
      ))}
    </tbody>
  </table>
</section>


  {/* Add Product */}
<section className="bg-white dark:bg-gray-800 p-4 rounded mb-6">
  <h2 className="text-xl mb-3">Add Product</h2>

  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
    <input
      placeholder="Style"
      className="p-2 border rounded"
      value={productForm.style}
      onChange={(e)=>setProductForm({...productForm, style:e.target.value})}
    />
    <input
      placeholder="Color"
      className="p-2 border rounded"
      value={productForm.color}
      onChange={(e)=>setProductForm({...productForm, color:e.target.value})}
    />
    <input
      placeholder="SKU"
      className="p-2 border rounded"
      value={productForm.sku}
      onChange={(e)=>setProductForm({...productForm, sku:e.target.value})}
    />
    <input
      placeholder="Price"
      type="number"
      className="p-2 border rounded"
      value={productForm.price}
      onChange={(e)=>setProductForm({...productForm, price:e.target.value})}
    />

    <select
      className="p-2 border rounded"
      value={productForm.vendor_id}
      onChange={(e)=>setProductForm({...productForm, vendor_id:e.target.value})}
    >
      <option value="">Select Vendor</option>
      {vendors.map(v=>(
        <option key={v.id} value={v.id}>{v.name}</option>
      ))}
    </select>
  </div>

  <button
    onClick={handleCreateProduct}
    className="bg-green-600 text-white px-3 py-2 rounded flex gap-1 items-center"
  >
    <PlusCircle size={16}/> Add Product
  </button>
</section>


          {/* Import & Convert */}
          <section className="bg-white dark:bg-gray-800 p-4 rounded mb-6">

            <div className="flex flex-wrap gap-2 items-center mb-3">

              <label className="bg-purple-600 text-white px-3 py-2 rounded cursor-pointer flex gap-1">
                <Upload size={16}/> Import B2B
                <input type="file" hidden accept=".csv" onChange={handleImportB2B}/>
              </label>

              <label className="bg-blue-600 text-white px-3 py-2 rounded cursor-pointer flex gap-1">
                <Upload size={16}/> Preview & Convert
                <input type="file" hidden accept=".csv" onChange={handlePreviewConvert}/>
              </label>

              <input className="p-2 border rounded" placeholder="Manufacturer override"
                     value={manufacturerOverride}
                     onChange={e=>setManufacturerOverride(e.target.value)}/>

              <label className="flex items-center gap-1">
                <input type="checkbox" checked={forceManufacturer} onChange={e=>setForceManufacturer(e.target.checked)}/>
                Force
              </label>

              <button onClick={handleExportJSON} className="bg-green-600 text-white px-3 py-2 rounded flex gap-1">
                <FileDown size={16}/> Export JSON
              </button>

            </div>

            {uploading && <p className="text-yellow-400">Processing…</p>}
          </section>

          {/* Preview Modal */}
          {showPreview && (
            <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
              <div className="bg-white dark:bg-gray-800 p-4 rounded w-4/5 max-h-[80vh] overflow-auto">

                <h3 className="text-lg mb-2">Preview</h3>

                <table className="w-full text-xs">
                  <thead><tr><th>Manufacturer</th><th>Style</th><th>SKU</th></tr></thead>
                  <tbody>
                    {previewRows.map((r,i)=>(
                      <tr key={i}>
                        <td>{r["~~Manufacturer"]}</td>
                        <td>{r["Style Name"]}</td>
                        <td>{r["SKU"]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <div className="flex justify-end gap-2 mt-3">
                  <button onClick={()=>setShowPreview(false)} className="border px-3 py-1 rounded">Close</button>
                  <button onClick={()=>handleConvertAndDownload(lastFile)} className="bg-blue-600 text-white px-3 py-1 rounded flex gap-1">
                    <DownloadCloud size={16}/> Convert & Download
                  </button>
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
