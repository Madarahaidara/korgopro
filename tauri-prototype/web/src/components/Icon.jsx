const iconFiles = {
  admin: 'admin.svg',
  building: 'building.svg',
  dashboard: 'dashboard.svg',
  document: 'document.svg',
  lock: 'lock.svg',
  receipt: 'receipt.svg',
  sale: 'sale.svg',
  settings: 'settings.svg',
  stock: 'stock.svg',
  treasury: 'treasury.svg',
  user: 'user.svg',
};

export default function Icon({ name, size = 18, ...props }) {
  const fileName = iconFiles[name] || 'dashboard.svg';
  return (
    <img
      src={`/icons/${fileName}`}
      width={size}
      height={size}
      aria-hidden="true"
      alt=""
      {...props}
    />
  );
}
