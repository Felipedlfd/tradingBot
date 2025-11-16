def calculate_position_size(capital, entry_price, sl, risk_fraction, leverage=1):
    risk_amount = capital * risk_fraction
    risk_per_unit = abs(entry_price - sl)
    base_size = risk_amount / risk_per_unit
    
    # Ajustar por apalancamiento
    adjusted_size = base_size * leverage
    return adjusted_size