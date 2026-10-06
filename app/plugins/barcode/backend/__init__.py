from app.core.hook_registry import hook_registry

def validate_barcodes(barcodes, **kwargs):
    print(f"[Barcode Plugin] Intercepted delivery barcodes: {barcodes}")
    # Example logic: ensure clean formats
    return [b.strip() for b in barcodes if b]

def validate_return_barcodes(barcodes, **kwargs):
    print(f"[Barcode Plugin] Intercepted return barcodes: {barcodes}")
    return [b.strip() for b in barcodes if b]

def initialize(app):
    print("[Barcode Plugin] Initializing hooks...")
    hook_registry.register_filter("before_tool_loan", validate_barcodes)
    hook_registry.register_filter("before_tool_return", validate_return_barcodes)
