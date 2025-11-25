import logging

def calculate_position_size(capital, entry_price, stop_loss, risk_fraction=0.01, max_leverage=1):
    """
    Calcula tamaño de posición con límite de margen REAL
    """
    # 1. Calcular tamaño basado en riesgo
    risk_amount = capital * risk_fraction
    risk_per_unit = abs(entry_price - stop_loss)
    if risk_per_unit == 0:
        return 0.0
    
    risk_based_size = risk_amount / risk_per_unit
    
    # 2. Calcular tamaño MÁXIMO permitido por margen
    max_position_value = capital * max_leverage * 0.9  # 90% del margen máximo
    margin_based_size = max_position_value / entry_price
    
    # 3. Usar el MÍNIMO de ambos valores (seguridad máxima)
    final_size = min(risk_based_size, margin_based_size)
    
    # 4. Logging para diagnóstico
    if final_size < risk_based_size:
        logging.warning(
            f"⚠️ Tamaño limitado por margen | "
            f"Riesgo: {risk_based_size:.6f} | "
            f"Margen: {margin_based_size:.6f} | "
            f"Final: {final_size:.6f}"
        )
    
    return final_size