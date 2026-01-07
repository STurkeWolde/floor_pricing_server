function ProductList({ products, vendors }) {
  const getVendorName = (id) => {
    const v = vendors.find((v) => v.id === id);
    return v ? v.name : "Unknown Vendor";
  };

  return (
    <div>
      <h3>Products</h3>
      <ul>
        {products.map((p) => (
          <li key={p.id}>
            {p.sku} - {p.style} ({p.color}) @ ${p.price} per {p.pricing_unit} —{" "}
            Vendor: {getVendorName(p.vendor_id)}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default ProductList;
