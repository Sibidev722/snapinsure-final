import random
from models.models import ZoneState

class SimpleLinearRegressor:
    def __init__(self, learning_rate=0.01, epochs=1000):
        self.weights = [0.0, 0.0, 0.0, 0.0, 0.0] # bias, w1, w2, w3, w4
        self.learning_rate = learning_rate
        self.epochs = epochs

    def predict_single(self, x):
        return self.weights[0] + sum(w * f for w, f in zip(self.weights[1:], x))

    def fit(self, X, y):
        # Stochastic Gradient Descent
        for _ in range(self.epochs):
            for xi, yi in zip(X, y):
                prediction = self.predict_single(xi)
                error = prediction - yi
                
                # Update bias
                self.weights[0] -= self.learning_rate * error
                # Update weights
                for j in range(len(xi)):
                    self.weights[j+1] -= self.learning_rate * error * xi[j]

class MLPricingEngine:
    def __init__(self):
        self.model = SimpleLinearRegressor()
        self.base_price = 10.0
        self._train_synthetic_data()

    def _train_synthetic_data(self):
        # Formula: premium = base_price * (1 + risk + weather_prob + disruption_history - safe_discount)
        X_train = []
        y_train = []
        for _ in range(500):
            risk = random.uniform(0, 1)
            weather = random.uniform(0, 1)
            history = random.uniform(0, 1)
            safe_discount = random.uniform(0, 0.5)
            
            x = [risk, weather, history, safe_discount]
            # Simulated target formula
            y = self.base_price * (1 + risk + weather + history - safe_discount)
            
            X_train.append(x)
            y_train.append(y)

        self.model.fit(X_train, y_train)
        print("ML Pricing Engine trained continuously on synthetic data successfully.")

    async def predict_premium(self, user_id: str, db) -> dict:
        # 1. Fetch real zone risk
        user_policies = await db["policies"].find({"user_id": user_id, "is_active": True}).to_list(length=100)
        
        risk_score = 0.0
        if user_policies:
            route_zones = user_policies[0].get("route_zones", [])
            if route_zones:
                if isinstance(route_zones, list):
                    zones = await db["zones"].find({"_id": {"$in": route_zones}}).to_list(length=100)
                    risk_sum = 0
                    for z in zones:
                         state = z.get("state", ZoneState.GREEN)
                         if state == ZoneState.RED: risk_sum += 1.0
                         elif state == ZoneState.YELLOW: risk_sum += 0.5
                    risk_score = risk_sum / len(zones) if zones else 0.0

        # 2. Simulate external factors
        weather_prob = random.uniform(0.1, 0.9)
        history = random.uniform(0.0, 0.5)
        safe_discount = 0.2 if risk_score < 0.2 else 0.0

        # 3. Model Inference
        x_input = [risk_score, weather_prob, history, safe_discount]
        premium = self.model.predict_single(x_input)
        
        # 4. Generate Explanation
        explanation = "Standard premium applied."
        if weather_prob > 0.7:
            explanation = "High rain risk increased premium"
        elif risk_score > 0.5:
            explanation = "High zone risk increased premium"
        elif history > 0.4:
            explanation = "Historical disruptions increased premium"
        elif safe_discount > 0:
            explanation = "Safe zone routing provided a discount"

        return {
            "premium": round(premium, 2),
            "explanation": explanation
        }

ml_pricing_engine = MLPricingEngine()
