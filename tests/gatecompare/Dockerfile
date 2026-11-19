# Reuse locked dependencies, real verifier and existing simulated source controls.
FROM epochguard-verifier:004g
COPY tests/gatecompare/ /app/gatecompare/
CMD ["python", "-m", "gatecompare.benchmark"]
