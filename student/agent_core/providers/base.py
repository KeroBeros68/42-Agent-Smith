"""Common provider interface: free-tier only, multi-key rotation on rate limit/quota,
stop_sequences to prevent tool-output hallucination, usage tracking
(tokens, retries, latency, request count) feeding StepMetrics.
"""
