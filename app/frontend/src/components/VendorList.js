function VendorList({ vendors }) {
  return (
    <div>
      <h3>Vendors</h3>
      <ul>
        {vendors.map((v) => (
          <li key={v.id}>
            <strong>{v.name}</strong> (Contact: {v.contact || "N/A"}, Phone:{" "}
            {v.phone || "N/A"})
          </li>
        ))}
      </ul>
    </div>
  );
}

export default VendorList;
