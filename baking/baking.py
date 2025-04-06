import streamlit as st
import requests
import json
import re
import pandas as pd
import time

# Set page config
st.set_page_config(
    page_title="Recipe Wizard",
    page_icon="🧁",
    layout="wide"
)

# CSS for better styling
st.markdown("""
<style>
    .main {
        padding: 2rem;
    }
    .recipe-container {
        background-color: #f9f7f3;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
        border-left: 5px solid #f0c05a;
    }
    .conversion-container {
        background-color: #f3f9f7;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
        border-left: 5px solid #5ac0f0;
    }
    .stButton button {
        background-color: #f0c05a;
        color: white;
        border: none;
    }
    .converter-result {
        font-size: 1.5rem;
        font-weight: bold;
        color: #2c3e50;
        padding: 10px;
        background-color: #ecf0f1;
        border-radius: 5px;
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Ingredient database
@st.cache_data
def load_ingredients_db():
    return {
        "all-purpose flour": {"density": 120, "temp_factor": 0.02},
        "bread flour": {"density": 127, "temp_factor": 0.02},
        "cake flour": {"density": 112, "temp_factor": 0.02},
        "whole wheat flour": {"density": 130, "temp_factor": 0.02},
        "granulated sugar": {"density": 200, "temp_factor": 0.005},
        "brown sugar": {"density": 220, "temp_factor": 0.01},
        "powdered sugar": {"density": 125, "temp_factor": 0.005},
        "butter": {"density": 227, "temp_factor": 0.05},
        "vegetable oil": {"density": 224, "temp_factor": 0.01},
        "milk": {"density": 242, "temp_factor": 0.02},
        "heavy cream": {"density": 238, "temp_factor": 0.02},
        "water": {"density": 237, "temp_factor": 0.01},
        "salt": {"density": 288, "temp_factor": 0.001},
        "baking powder": {"density": 192, "temp_factor": 0.005},
        "baking soda": {"density": 220, "temp_factor": 0.005},
        "cocoa powder": {"density": 106, "temp_factor": 0.02},
        "honey": {"density": 340, "temp_factor": 0.03},
        "maple syrup": {"density": 322, "temp_factor": 0.03},
        "rolled oats": {"density": 85, "temp_factor": 0.01},
        "chopped nuts": {"density": 113, "temp_factor": 0.01},
        "chocolate chips": {"density": 170, "temp_factor": 0.01},
        "eggs": {"density": 50, "temp_factor": 0.02, "unit": "each"},
        "vanilla extract": {"density": 4.2, "temp_factor": 0.01, "unit": "teaspoon"},
        "yeast": {"density": 3, "temp_factor": 0.005, "unit": "teaspoon"},
    }

# Conversion factors
@st.cache_data
def get_conversion_factors():
    return {
        "cup": 1,
        "cups": 1,
        "tablespoon": 0.0625,
        "tablespoons": 0.0625,
        "tbsp": 0.0625,
        "teaspoon": 0.0208333,
        "teaspoons": 0.0208333,
        "tsp": 0.0208333,
        "fluid ounce": 0.125,
        "fluid ounces": 0.125,
        "fl oz": 0.125,
        "milliliter": 0.00422675,
        "milliliters": 0.00422675,
        "ml": 0.00422675,
        "liter": 4.22675,
        "liters": 4.22675,
        "l": 4.22675,
        "pint": 2,
        "pints": 2,
        "pt": 2,
        "quart": 4,
        "quarts": 4,
        "qt": 4,
        "gallon": 16,
        "gallons": 16,
        "gal": 16
    }

# Ollama API functions
def generate_recipe(prompt, model="tinyllama"):
    """Get a recipe from Ollama's TinyLLama model"""
    try:
        api_url = "http://localhost:11434/api/generate"
        payload = {
            "model": model,
            "prompt": f"Generate a detailed recipe for {prompt}. Include ingredients with measurements and step-by-step instructions.",
            "stream": False
        }
        
        response = requests.post(api_url, json=payload)
        if response.status_code == 200:
            result = response.json()
            return result.get("response", "Sorry, I couldn't generate a recipe.")
        else:
            return f"Error: {response.status_code}. Make sure Ollama is running with TinyLLama model."
    except Exception as e:
        return f"Error connecting to Ollama: {str(e)}"

def convert_to_grams(quantity, unit, ingredient, temperature=20):
    """Convert a measurement to grams considering temperature effects"""
    ingredients_db = load_ingredients_db()
    volume_to_cups = get_conversion_factors()
    
    # Normalize ingredient name
    ingredient = ingredient.lower().strip()
    unit = unit.lower().strip()
    
    # Check if ingredient exists in database
    if ingredient not in ingredients_db:
        return None
        
    # Get density and temperature factor
    density = ingredients_db[ingredient]["density"]
    temp_factor = ingredients_db[ingredient]["temp_factor"]
    
    # Apply temperature adjustment to density
    # Assume density was measured at 20°C
    temp_diff = temperature - 20
    density_adjustment = 1 + (temp_factor * temp_diff / 10)
    adjusted_density = density * density_adjustment
    
    # Handle special units
    if "unit" in ingredients_db[ingredient]:
        special_unit = ingredients_db[ingredient]["unit"]
        if unit == special_unit or unit == special_unit + "s":
            return quantity * adjusted_density
            
    # Convert volume measurements to cups first, then to grams
    if unit in volume_to_cups:
        cups = quantity * volume_to_cups[unit]
        return cups * adjusted_density
        
    # Handle weight measurements
    elif unit in ["gram", "g", "grams"]:
        return quantity
    elif unit in ["kilogram", "kg", "kilograms"]:
        return quantity * 1000
    elif unit in ["ounce", "oz", "ounces"]:
        return quantity * 28.35
    elif unit in ["pound", "lb", "pounds"]:
        return quantity * 453.59
        
    return None

def convert_recipe_to_grams(recipe_text, temperature=20):
    """Parse recipe and add gram measurements"""
    lines = recipe_text.strip().split("\n")
    converted_lines = []
    
    # Regular expression to match ingredient lines
    ingredient_pattern = r"([\d./\s]+)\s+(\w+(?:\s+\w+)?)\s+(?:of\s+)?(.+?)(?:,|$|\n)"
    
    for line in lines:
        if not line.strip():
            converted_lines.append(line)
            continue
            
        # Look for ingredient patterns
        matches = re.finditer(ingredient_pattern, line)
        modified_line = line
        
        for match in matches:
            quantity_str, unit, ingredient = match.groups()
            
            # Convert quantity to float
            quantity_str = quantity_str.strip()
            try:
                # Handle fractions
                if "/" in quantity_str:
                    if " " in quantity_str:  # Mixed number (e.g., "1 1/2")
                        whole, fraction = quantity_str.split(" ", 1)
                        num, denom = fraction.split("/")
                        quantity = float(whole) + float(num) / float(denom)
                    else:  # Simple fraction (e.g., "1/2")
                        num, denom = quantity_str.split("/")
                        quantity = float(num) / float(denom)
                else:
                    quantity = float(quantity_str)
                    
                # Try to convert to grams
                grams = convert_to_grams(quantity, unit, ingredient, temperature)
                if grams is not None:
                    # Round to 1 decimal place
                    grams = round(grams, 1)
                    # Add gram measurement in parentheses after the original text
                    full_match = match.group(0)
                    replacement = f"{full_match} ({grams}g)"
                    modified_line = modified_line.replace(full_match, replacement, 1)
            except:
                # If conversion fails, just keep the original text
                pass
                
        converted_lines.append(modified_line)
                
    return "\n".join(converted_lines)

# Initialize session state variables
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'recipe_db' not in st.session_state:
    st.session_state.recipe_db = {}

# App title
st.title("🧁 Recipe Wizard")
st.markdown("### Your AI-Powered Recipe Assistant with Precision Conversion")

# Create two columns for layout
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("## Recipe Generator")
    
    recipe_input = st.text_input("What would you like to make today?", 
                                placeholder="e.g. chocolate chip cookies, chicken curry, vegan lasagna...")
    
    col_temp, col_btn = st.columns([1, 1])
    with col_temp:
        kitchen_temp = st.slider("Kitchen Temperature (°C)", 15, 35, 20)
        
    with col_btn:
        st.write("")
        st.write("")
        recipe_button = st.button("Generate Recipe", use_container_width=True)
    
    if recipe_button and recipe_input:
        with st.spinner("Generating your recipe with precise measurements..."):
            # Get recipe from Ollama
            recipe_output = generate_recipe(recipe_input)
            
            # Add gram conversions
            converted_recipe = convert_recipe_to_grams(recipe_output, kitchen_temp)
            
            # Store in session state
            recipe_key = f"recipe_{len(st.session_state.recipe_db) + 1}"
            st.session_state.recipe_db[recipe_key] = {
                "name": recipe_input,
                "recipe": converted_recipe
            }
            
            # Add to chat history
            st.session_state.chat_history.append({"role": "user", "content": f"Generate recipe for {recipe_input}"})
            st.session_state.chat_history.append({"role": "assistant", "content": converted_recipe})
    
    # Display chat history
    st.markdown("### Your Recipe Conversations")
    
    for message in st.session_state.chat_history:
        if message["role"] == "user":
            st.markdown(f"**You:** {message['content']}")
        else:
            with st.container(border=True):
                st.markdown(f"{message['content']}")

with col2:
    st.markdown("## Ingredient Converter")
    
    # Fixed: Removed the class_ parameter which was causing the error
    converter_container = st.container(border=True)
    with converter_container:
        st.markdown("### Convert Single Ingredient")
        
        # Get ingredient options from database
        ingredients = sorted(list(load_ingredients_db().keys()))
        selected_ingredient = st.selectbox("Select Ingredient", ingredients)
        
        # Input for quantity and unit
        col_qty, col_unit = st.columns(2)
        with col_qty:
            quantity = st.number_input("Quantity", min_value=0.1, value=1.0, step=0.1)
            
        with col_unit:
            units = sorted(list(get_conversion_factors().keys()) + ["gram", "g", "ounce", "oz", "pound", "lb"])
            unit = st.selectbox("Unit", units)
        
        convert_temp = st.slider("Conversion Temperature (°C)", 15, 35, 20)
        
        if st.button("Convert to Grams", use_container_width=True):
            grams = convert_to_grams(quantity, unit, selected_ingredient, convert_temp)
            if grams is not None:
                grams_rounded = round(grams, 1)
                st.markdown(f'<div class="converter-result">{quantity} {unit} of {selected_ingredient} = {grams_rounded}g</div>', unsafe_allow_html=True)
            else:
                st.error(f"Cannot convert {selected_ingredient} with the selected unit. Please try another unit.")
    
    # Saved recipes section
    st.markdown("### Saved Recipes")
    
    for key, recipe_data in st.session_state.recipe_db.items():
        with st.expander(recipe_data["name"]):
            st.markdown(recipe_data["recipe"])

    # Information about the app
    with st.expander("About Recipe Wizard"):
        st.markdown("""
        **Recipe Wizard** combines AI-powered recipe generation with precision baking conversion.
        
        **Features:**
        - Generate detailed recipes for any dish using TinyLLama AI
        - Automatic conversion of ingredient measurements to precise grams
        - Temperature-adjusted density calculations for maximum accuracy
        - Single ingredient converter for quick reference
        
        **How to use:**
        1. Enter a dish name in the recipe generator
        2. Adjust your kitchen temperature if needed
        3. Click "Generate Recipe" to get a detailed recipe with gram conversions
        4. Use the ingredient converter for single conversions
        
        **Note:** Requires Ollama running locally with the TinyLLama model.
        Install with: `ollama pull tinyllama`
        """)
        
    # Technical details
    with st.expander("Technical Information"):
        st.markdown("""
        **Technologies used:**
        - Streamlit for the web interface
        - Ollama with TinyLLama model for recipe generation
        - Custom conversion algorithm accounting for:
          - Ingredient-specific densities
          - Temperature effects on ingredient volumes
          - Various measurement units
        
        **Conversion Database:**
        """)
        
        # Show ingredient database as a table
        ingredients_data = []
        for ing, data in load_ingredients_db().items():
            ingredients_data.append({
                "Ingredient": ing,
                "Density (g/cup)": data["density"],
                "Temp Factor": data["temp_factor"],
                "Special Unit": data.get("unit", "-")
            })
            
        df = pd.DataFrame(ingredients_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

# Footer
st.markdown("---")
st.markdown("Recipe Wizard © 2025 | Precision Baking with AI")