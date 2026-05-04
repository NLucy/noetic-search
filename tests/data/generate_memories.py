#!/usr/bin/env python
"""Generate realistic software engineering knowledge base memories."""

import json
import random
from typing import Any

# Domain knowledge templates
TOPICS = {
    "python": [
        "How do I install packages with pip in a virtual environment?",
        "What's the difference between list and tuple in Python?",
        "Why am I getting a KeyError when accessing dictionary keys?",
        "How to handle async/await in Python properly?",
        "Best practices for Python exception handling",
        "Understanding Python decorators and their use cases",
        "How to optimize Python code for performance?",
        "Setting up pytest for unit testing in Python",
        "Using type hints in Python 3.10+",
        "Memory management and garbage collection in Python",
    ],
    "javascript": [
        "What is the difference between let, const, and var?",
        "How do promises work in JavaScript?",
        "Understanding this context in JavaScript functions",
        "React hooks vs class components - which to use?",
        "How to prevent memory leaks in JavaScript applications?",
        "Async await vs promise chaining in Node.js",
        "JavaScript closure examples and common pitfalls",
        "How to properly handle errors in async JavaScript?",
        "Understanding the JavaScript event loop",
        "Best practices for state management in React",
    ],
    "database": [
        "PostgreSQL indexing strategies for large tables",
        "How to optimize slow SQL queries?",
        "Understanding database transactions and ACID properties",
        "MongoDB vs PostgreSQL - when to use each?",
        "Preventing SQL injection attacks",
        "Database connection pooling best practices",
        "How to handle database schema migrations?",
        "Redis caching strategies for API responses",
        "Understanding database normalization vs denormalization",
        "Handling database deadlocks in production",
    ],
    "docker": [
        "How to write an efficient Dockerfile?",
        "Docker compose networking between containers",
        "Understanding Docker layers and caching",
        "Best practices for Docker image security",
        "How to debug containers that fail to start?",
        "Docker volume management and persistence",
        "Optimizing Docker build times in CI/CD",
        "Handling secrets in Docker containers",
        "Docker multi-stage builds explained",
        "Container resource limits and monitoring",
    ],
    "kubernetes": [
        "Understanding Kubernetes pods, deployments, and services",
        "How to configure Kubernetes ingress?",
        "Kubernetes horizontal pod autoscaling setup",
        "Debugging CrashLoopBackOff errors",
        "Best practices for Kubernetes secrets management",
        "Setting up persistent volumes in Kubernetes",
        "Kubernetes resource requests vs limits",
        "How to perform rolling updates without downtime?",
        "Understanding Kubernetes namespaces",
        "Monitoring Kubernetes clusters with Prometheus",
    ],
    "api": [
        "RESTful API design best practices",
        "How to implement API rate limiting?",
        "GraphQL vs REST - when to use each?",
        "API versioning strategies",
        "Handling API authentication with JWT tokens",
        "Best practices for API error responses",
        "How to document APIs with OpenAPI/Swagger?",
        "Implementing pagination in REST APIs",
        "API caching strategies for performance",
        "How to handle API deprecation gracefully?",
    ],
    "testing": [
        "Writing effective unit tests",
        "Integration testing vs end-to-end testing",
        "How to mock external dependencies in tests?",
        "Test-driven development workflow",
        "Using fixtures in pytest",
        "How to test async code properly?",
        "Code coverage - what percentage is enough?",
        "Testing database interactions",
        "How to write maintainable test code?",
        "Snapshot testing for UI components",
    ],
    "security": [
        "How to prevent XSS attacks in web applications?",
        "Understanding CSRF protection",
        "Best practices for password hashing",
        "How to implement OAuth 2.0 authentication?",
        "Securing API endpoints",
        "Understanding CORS and same-origin policy",
        "How to handle sensitive data in logs?",
        "SSL/TLS certificate management",
        "Preventing common security vulnerabilities",
        "Security headers for web applications",
    ],
}

ANSWER_TEMPLATES = {
    "solution": [
        "You can solve this by {solution}. This approach works because {reason}.",
        "The recommended way is to {solution}. Make sure to {caveat}.",
        "I've found that {solution} works well in production. We use this at scale.",
        "After debugging this myself, {solution} fixed it. The root cause was {cause}.",
        "Try {solution}. This is mentioned in the official documentation.",
    ],
    "explanation": [
        "This happens because {reason}. The underlying mechanism is {detail}.",
        "The key difference is {point1} vs {point2}. Choose based on {criteria}.",
        "Under the hood, {mechanism}. That's why you see {behavior}.",
        "This is actually a common misconception. The reality is {truth}.",
        "From my experience, {observation}. This is because {reason}.",
    ],
    "problem": [
        "I'm seeing the same issue. Getting {error} when {action}.",
        "This broke after upgrading to version {version}. Anyone else?",
        "Running into {problem} in production. Impact: {impact}.",
        "Reproducible bug: {steps}. Expected {expected}, got {actual}.",
        "Critical issue: {problem}. Need urgent help, affecting users.",
    ],
    "discussion": [
        "I think the better approach is {opinion} because {reason}.",
        "Both options have tradeoffs. {option1} is faster but {tradeoff}.",
        "In my team we decided to {decision} after {consideration}.",
        "The industry is moving toward {trend}. See {reference}.",
        "Controversial take: {opinion}. Here's why: {justification}.",
    ],
}

SOURCES = ["stackoverflow", "github", "docs", "blog", "forum", "slack"]
QUALITY = ["high", "medium", "low"]
STATUS = ["solved", "unsolved", "discussing", "archived"]

def generate_memory(id_num: int, topic: str, question: str) -> dict[str, Any]:
    """Generate a single memory."""
    answer_type = random.choice(list(ANSWER_TEMPLATES.keys()))
    template = random.choice(ANSWER_TEMPLATES[answer_type])

    # Fill in template (simplified)
    content = f"{question} " + template.format(
        solution="use the standard library method",
        reason="it's optimized and well-tested",
        caveat="handle edge cases properly",
        cause="a race condition in async code",
        point1="performance",
        point2="developer experience",
        criteria="your use case",
        detail="the event loop processing",
        mechanism="lazy evaluation",
        behavior="this unexpected result",
        truth="it depends on the runtime",
        observation="this pattern works well",
        error="Connection refused",
        action="connecting to the database",
        version="v2.5.0",
        problem="memory leak",
        impact="50% of requests failing",
        steps="start app, make request, observe crash",
        expected="200 OK",
        actual="500 Internal Server Error",
        opinion="microservices over monolith",
        tradeoff="adds complexity",
        option1="caching",
        decision="use TypeScript",
        consideration="team discussion",
        trend="serverless",
        reference="recent conference talks",
        justification="reduces bugs",
    )

    return {
        "id": f"mem-{topic}-{id_num:04d}",
        "text": content,
        "metadata": {
            "topic": topic,
            "source": random.choice(SOURCES),
            "quality": random.choice(QUALITY),
            "status": random.choice(STATUS),
            "votes": random.randint(0, 100),
            "answer_type": answer_type,
        }
    }

def generate_corpus(total: int = 1000) -> list[dict[str, Any]]:
    """Generate full corpus."""
    corpus = []
    memories_per_topic = total // len(TOPICS)

    for topic, questions in TOPICS.items():
        for i in range(memories_per_topic):
            question = random.choice(questions)
            memory = generate_memory(i, topic, question)
            corpus.append(memory)

    # Shuffle to mix topics
    random.shuffle(corpus)

    return corpus

def main():
    random.seed(42)  # Reproducible

    corpus = generate_corpus(1000)

    output = {
        "corpus": corpus,
        "queries": {
            "python_venv": "How do I set up a Python virtual environment and install packages?",
            "async_errors": "My async JavaScript code is throwing errors, how do I debug it?",
            "database_slow": "PostgreSQL queries are running slow, how to optimize performance?",
            "docker_security": "What are the security best practices for Docker containers?",
            "kubernetes_crash": "My Kubernetes pods keep crashing, how do I debug this?",
            "api_design": "What are the best practices for designing RESTful APIs?",
            "testing_mocks": "How do I properly mock external dependencies in my tests?",
            "security_xss": "How can I prevent XSS attacks in my web application?",
        },
        "metadata": {
            "total_memories": len(corpus),
            "topics": list(TOPICS.keys()),
            "generated_with_seed": 42,
        }
    }

    # Save
    with open("software_kb.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"Generated {len(corpus)} memories")
    print(f"Topics: {', '.join(TOPICS.keys())}")
    print(f"Saved to software_kb.json")

if __name__ == "__main__":
    main()
