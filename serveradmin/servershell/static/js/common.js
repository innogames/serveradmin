function array_min(arr)
{   
    var local_min = null;
    for(var i = 0; i < arr.length; i++) {
        if (local_min == null) {
            local_min = arr[i];
        } else {
            if (arr[i] < local_min) {
                local_min = arr[i];
            }
        }
    }
    return local_min;
}

function is_digit(x)
{
    return x == '0' || x == '1' || x == '2' || x == '3' || x == '4' ||
        x == '5' || x == '6' || x == '7' || x == '8' || x == '9';
}

