import csv
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ExpenseForm
from .models import Category, Expense, MonthlyBudget


def parse_month(value):
    """Turn '2026-11' into (2026, 11). Return None if the value is invalid."""
    try:
        year, month = value.split("-")
        year, month = int(year), int(month)
        if 1 <= month <= 12:
            return year, month
    except (ValueError, AttributeError):
        pass
    return None


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Account created. Welcome to SpendWise!")
        return redirect("dashboard")
    return render(request, "registration/register.html", {"form": form})


@login_required
def dashboard(request):
    today = timezone.localdate()
    year, month = parse_month(request.GET.get("month")) or (today.year, today.month)

    # Only this user's expenses, only the chosen month.
    expenses = Expense.objects.filter(
        user=request.user, date__year=year, date__month=month
    )

    total = expenses.aggregate(total=Sum("amount"))["total"] or 0

    by_category = (
        expenses.values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )

    # Get the budget for the selected month.
    budget = MonthlyBudget.objects.filter(
        user=request.user,
        month__year=year,
        month__month=month,
    ).first()

    budget_amount = budget.amount if budget else 0
    remaining = budget_amount - total if budget else 0

    # Budget warning
    budget_warning = ""

    if budget:
        if total >= budget_amount:
            budget_warning = "over"
        elif total >= budget_amount * Decimal("0.80"):
            budget_warning = "warning"

    context = {
        "month_value": f"{year}-{month:02d}",
        "total": total,
        "count": expenses.count(),
        "top_category": by_category[0]["category__name"] if by_category else "-",
        "by_category": by_category,
        "recent": expenses.select_related("category")[:5],

        # Budget information
        "budget": budget,
        "budget_amount": budget_amount,
        "remaining": remaining,
        "budget_set": bool(budget),
        "budget_warning": budget_warning,
    }

    return render(request, "tracker/dashboard.html", context)


@login_required
def chart_data(request):
    """JSON endpoint used by static/js/main.js to draw the chart."""
    today = timezone.localdate()
    year, month = parse_month(request.GET.get("month")) or (today.year, today.month)
    rows = (
        Expense.objects.filter(user=request.user, date__year=year, date__month=month)
        .values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    return JsonResponse(
        {
            "labels": [r["category__name"] for r in rows],
            "values": [float(r["total"]) for r in rows],
        }
    )


@login_required
def expense_list(request):
    expenses = Expense.objects.filter(user=request.user).select_related("category")

    month_value = request.GET.get("month", "")
    category_id = request.GET.get("category", "")
    search_query = request.GET.get("q", "").strip()

    parsed = parse_month(month_value)
    if parsed:
        expenses = expenses.filter(date__year=parsed[0], date__month=parsed[1])
    if category_id.isdigit():
        expenses = expenses.filter(category_id=int(category_id))
    if search_query:
        expenses = expenses.filter(title__icontains=search_query)

    context = {
        "expenses": expenses,
        "categories": Category.objects.all(),
        "month_value": month_value,
        "selected_category": category_id,
        "search_query": search_query,
        "total": expenses.aggregate(total=Sum("amount"))["total"] or 0,
    }
    return render(request, "tracker/expense_list.html", context)

@login_required
def export_expenses(request):
    expenses = Expense.objects.filter(
        user=request.user
    ).select_related("category")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="expenses.csv"'

    writer = csv.writer(response)
    writer.writerow(["Date", "Title", "Category", "Amount", "Note"])

    for expense in expenses:
        writer.writerow([
            expense.date,
            expense.title,
            expense.category.name,
            expense.amount,
            expense.note,
        ])

    return response


@login_required
def expense_create(request):
    form = ExpenseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        expense = form.save(commit=False)
        expense.user = request.user  # never trust the browser for the owner
        expense.save()
        messages.success(request, "Expense added.")
        return redirect("expense_list")
    return render(request, "tracker/expense_form.html", {"form": form, "title": "Add expense"})


@login_required
def expense_update(request, pk):
    # user=request.user -> other people's expenses give a 404
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    form = ExpenseForm(request.POST or None, instance=expense)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Expense updated.")
        return redirect("expense_list")
    return render(request, "tracker/expense_form.html", {"form": form, "title": "Edit expense"})


@login_required
def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    if request.method == "POST":
        expense.delete()
        messages.success(request, "Expense deleted.")
        return redirect("expense_list")
    return render(request, "tracker/expense_confirm_delete.html", {"expense": expense})

@login_required
def budget(request):
    today = timezone.localdate()

    if request.method == "POST":
        month_value = request.POST.get("month")
        amount = request.POST.get("amount")

        parsed = parse_month(month_value)

        if parsed and amount:
            year, month = parsed

            MonthlyBudget.objects.update_or_create(
                user=request.user,
                month=timezone.datetime(year, month, 1).date(),
                defaults={"amount": amount},
            )

            messages.success(request, "Monthly budget saved.")
            return redirect("dashboard")

        messages.error(request, "Please enter a valid month and budget amount.")

    return render(
        request,
        "tracker/budget.html",
        {
            "month_value": f"{today.year}-{today.month:02d}",
        },
    )
