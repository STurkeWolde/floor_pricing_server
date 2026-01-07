import React, { useState } from "react";
import { Upload, FileSpreadsheet, Download } from "lucide-react";

const API_URL = "http://127.0.0.1:8000/b2b";

export default function B2BImport() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [convertedFile, setConvertedFile] = useState(null);

  const handleUpload = async (endpoint) => {
    if (!file) {
      setMessage("⚠️ Please select a CSV file first.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setLoading(true);
    setMessage("");

    try {
      const response = await fetch(`${API_URL}/${endpoint}`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("Server error");

      // If converting, allow file download
      if (endpoint === "convert-to-b2b") {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "converted_b2b.csv";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setConvertedFile("converted_b2b.csv");
        setMessage("✅ File converted successfully. Downloaded as converted_b2b.csv");
      } else {
        const data = await response.json();
        setMessage(data.status || "✅ Import completed successfully!");
      }
    } catch (err) {
      setMessage("❌ Failed to upload. Please check the CSV format or backend logs.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 p-6 transition-colors">
      <h3 className="text-lg font-semibold mb-4 text-gray-700 dark:text-gray-300 flex items-center gap-2">
        <FileSpreadsheet size={20} />
        B2B Import & Conversion
      </h3>

      <div className="flex flex-col sm:flex-row items-center gap-3">
        <input
          type="file"
          accept=".csv"
          onChange={(e) => setFile(e.target.files[0])}
          className="border border-gray-300 dark:border-gray-600 rounded-md p-2 text-sm bg-gray-50 dark:bg-gray-700 w-full sm:w-auto"
        />

        <div className="flex gap-2">
          <button
            onClick={() => handleUpload("import/csv")}
            disabled={loading}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md text-sm transition disabled:opacity-50"
          >
            <Upload size={16} />
            {loading ? "Importing..." : "Import B2B CSV"}
          </button>

          <button
            onClick={() => handleUpload("convert-to-b2b")}
            disabled={loading}
            className="flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-md text-sm transition disabled:opacity-50"
          >
            <Download size={16} />
            {loading ? "Converting..." : "Convert to B2B"}
          </button>
        </div>
      </div>

      {message && (
        <div
          className={`mt-4 text-sm p-3 rounded-md ${
            message.startsWith("✅")
              ? "bg-green-100 text-green-700 dark:bg-green-800 dark:text-green-200"
              : message.startsWith("❌")
              ? "bg-red-100 text-red-700 dark:bg-red-800 dark:text-red-200"
              : "bg-yellow-100 text-yellow-700 dark:bg-yellow-800 dark:text-yellow-200"
          }`}
        >
          {message}
        </div>
      )}
    </div>
  );
}
