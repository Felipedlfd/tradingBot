def calculate_position_size(capital, entry_price, stop_loss, risk_fraction=0.01):
    risk_amount = capital * risk_fraction
    risk_per_unit = abs(entry_price - stop_loss)
    if risk_per_unit == 0:
        return 0
    size = risk_amount / risk_per_unit
    return size