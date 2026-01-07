import React, { useState } from "react";

function ConvertToB2B() {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState("");

  const handleConvert = async () => {
    if (!file) return alert("Please choose a CSV file first.");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("http://127.0.0.1:8000/b2b/convert-to-b2b", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        throw new Error(`Failed: ${res.statusText}`);
      }

      // Download converted file
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${file.name.replace(".csv", "")}_B2B.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);

      setStatus("✅ File converted and downloaded successfully!");
    } catch (err) {
      console.error(err);
      setStatus("❌ Failed to convert file. Please check format or backend logs.");
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 transition-colors">
      <h3 className="text-lg font-semibold mb-4 text-gray-700 dark:text-gray-300">
        Convert Any CSV to B2B Format
      </h3>
      <input
        type="file"
        accept=".csv"
        onChange={(e) => setFile(e.target.files[0])}
        className="mb-4 block w-full text-sm text-gray-700 dark:text-gray-200"
      />
      <button
        onClick={handleConvert}
        className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 transition"
      >
        Convert & Download
      </button>
      {status && (
        <p className="mt-4 text-sm font-medium text-gray-600 dark:text-gray-300">{status}</p>
      )}
    </div>
  );
}

export default ConvertToB2B;
