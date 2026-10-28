def greet(name: str) -> str:
    """이름을 받아 인사말을 돌려준다. 빈 이름은 ValueError."""
    name = name.strip()
    if not name:
        raise ValueError("name must not be empty")
    return f"Hello, {name}!"


def main() -> None:
    print(greet("Rust"))


if __name__ == "__main__":
    main()
