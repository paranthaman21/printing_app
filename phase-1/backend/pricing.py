import math

def calculate_total(pages, copies, color, sides):
    """
    Calculate the total price based on printing options.
    
    Args:
        pages (int): Number of pages in the document.
        copies (int): Number of copies requested.
        color (str): 'BW' or 'COLOR'.
        sides (str): 'SINGLE' or 'DOUBLE'.
        
    Returns:
        dict: Breakdown of calculation including total price.
    """
    # Validation / Logic normalization
    if sides == 'DOUBLE':
        sheets_per_copy = math.ceil(pages / 2)
    else:
        sheets_per_copy = pages
        
    total_sheets = sheets_per_copy * copies
    
    # Price rates
    if color == 'BW':
        if sides == 'SINGLE':
            rate = 3
            # Logic: 3 per page (since 1 sheet = 1 page) * copies
            # If standard is per page: 3 * pages * copies
            # If standard is per sheet: 3 * sheets * copies. 
            # Requirement says: "B&W single: ₹3/page" -> 3 * pages * copies. 
            # For header sheets logic, simple enough.
            price = 3 * pages * copies
        else:
            # "B&W double: ₹5/sheet"
            rate = 5
            price = 5 * sheets_per_copy * copies
    else: # COLOR
        if sides == 'SINGLE':
            # "Colour single: ₹10/page"
            rate = 10
            price = 10 * pages * copies
        else:
            # "Colour double: ₹18/sheet"
            rate = 18
            price = 18 * sheets_per_copy * copies

    return {
        "pages": pages,
        "copies": copies,
        "color": color,
        "sides": sides,
        "sheets_per_copy": sheets_per_copy,
        "total_sheets": total_sheets,
        "price": price
    }
