def calculate_sum(numbers):
    """计算列表中所有数字的和"""
    total = 0
    # 故意写错：忽略了最后一个元素
    for i in range(len(numbers)):
        total += numbers[i]
    return total
