from machia.tools import ToolRegistry
from machia.tools.system import SYS_INFO
from machia.tools.fs import FS_LIST


def main():
    reg = ToolRegistry()
    reg.register(SYS_INFO)
    reg.register(FS_LIST)

    print("=== Registered tools ===")
    for spec in reg.all():
        print(f"  - {spec.name} (risk={spec.risk})")
        print(f"      {spec.description}")

    print("\n=== Tool schemas (what the model sees) ===")
    import json
    print(json.dumps(reg.schemas(), indent=2))

    print("\n=== Run sys_info ===")
    print(reg.run("sys_info", {}))

    print("\n=== Run fs_list on workspace root ===")
    print(reg.run("fs_list", {"path": "."}))

    print("\n=== Run fs_list on a subfolder ===")
    print(reg.run("fs_list", {"path": "downloads"}))

    print("\n=== Path jail test (should fail) ===")
    try:
        reg.run("fs_list", {"path": "../../Windows"})
    except PermissionError as e:
        print(f"Blocked as expected: {e}")


if __name__ == "__main__":
    main()