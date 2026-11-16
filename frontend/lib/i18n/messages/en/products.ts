import type { products as es } from "../es/products";
import type { Strings } from "../types";

export const products: Strings<typeof es> = {
  form: {
    nameRequired: "The name is required.",
    priceInvalid: "The price isn't valid.",
    saveFailed: "Couldn't save the product.",
    description: "Description",
    price: "Price",
    currency: "Currency",
    productUrl: "Product URL",
    imageUrl: "Image URL",
    active: "Active (shown in the catalog)",
    create: "Create product",
  },
  filters: {
    all: "All",
    active: "Active",
    inactive: "Inactive",
  },
  title: "Products",
  new: "New product",
  edit: "Edit product",
  filterLabel: "Filter products",
  loadFailed: "Couldn't load the products.",
  empty: "No products yet.",
  active: "Active",
  inactive: "Inactive",
  deleteConfirm: "Delete \"{name}\"?",
  description: "Description",
};
